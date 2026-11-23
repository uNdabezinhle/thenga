"""Cart resolution, merge, shipping generation, stock checks."""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch

from apps.catalogue.models import Inventory, Product, ProductVariant
from apps.core.exceptions import CartItemOutOfStock, CartSessionInvalid
from apps.pricing.services import Line, compute_totals

from .models import Cart, CartDiscount, CartItem, Coupon, ShippingEstimate


def cart_queryset():
    return Cart.objects.prefetch_related(
        Prefetch(
            "items",
            queryset=CartItem.objects.select_related(
                "product", "product__brand", "variant", "variant__inventory"
            ),
        ),
        "discounts",
        "shipping_estimates",
    )


def get_or_create_cart(request) -> Cart:
    """Resolve cart for authenticated user or guest session."""
    if request.user and request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(
            user=request.user,
            is_active=True,
            defaults={"session_id": None},
        )
        return cart_queryset().get(pk=cart.pk)

    sid = getattr(request, "cart_session_id", None)
    if not sid or not getattr(request, "cart_session_valid", False):
        raise CartSessionInvalid("Provide a valid X-Cart-Session header.")
    cart, _ = Cart.objects.get_or_create(
        session_id=sid,
        is_active=True,
        defaults={"user": None},
    )
    return cart_queryset().get(pk=cart.pk)


def ensure_shipping_estimates(cart: Cart) -> list[ShippingEstimate]:
    """Generate default domestic rates if none exist (REKA-FR-CART-012)."""
    existing = list(cart.shipping_estimates.all())
    if existing:
        return existing
    from apps.orders.couriers import get_courier

    created = []
    for i, quote in enumerate(get_courier().quote()):
        name, price, days = quote.method_name, quote.price, quote.estimated_days
        created.append(
            ShippingEstimate.objects.create(
                cart=cart,
                method_name=name,
                price=price,
                estimated_days=days,
                is_selected=(i == 0),
            )
        )
    return created


def available_stock(variant: ProductVariant | None, product: Product) -> int:
    if variant is not None:
        inv = getattr(variant, "inventory", None)
        if inv is None:
            try:
                inv = Inventory.objects.get(variant=variant)
            except Inventory.DoesNotExist:
                return 0
        return inv.available
    # product-level fallback: sum variants
    total = 0
    for v in product.variants.select_related("inventory").all():
        if hasattr(v, "inventory") and v.inventory:
            total += v.inventory.available
    return total


def assert_stock(product: Product, variant: ProductVariant | None, resulting_qty: int):
    avail = available_stock(variant, product)
    if resulting_qty > avail:
        raise CartItemOutOfStock(
            detail=f"Only {avail} of this item are available.",
            details={"available": avail, "requested": resulting_qty},
            field="quantity",
        )


def cart_totals(cart: Cart):
    lines = [
        Line(unit_price=i.unit_price_snapshot, quantity=i.quantity) for i in cart.items.all()
    ]
    discounts = [
        (d.discount_type, d.amount) for d in cart.discounts.all()
    ]
    shipping = Decimal("0.00")
    selected = cart.shipping_estimates.filter(is_selected=True).first()
    if selected:
        shipping = selected.price
    return compute_totals(lines=lines, discounts=discounts, shipping=shipping)


@transaction.atomic
def merge_carts(user, session_id: str) -> Cart:
    """Transfer guest cart into the authenticated user's cart.

    Ownership: caller must present the session they claim (verified by middleware).
    """
    try:
        guest = Cart.objects.select_for_update().get(
            session_id=session_id, is_active=True, user__isnull=True
        )
    except Cart.DoesNotExist:
        # nothing to merge
        cart, _ = Cart.objects.get_or_create(user=user, is_active=True)
        return cart_queryset().get(pk=cart.pk)

    user_cart, _ = Cart.objects.select_for_update().get_or_create(
        user=user, is_active=True, defaults={"session_id": None}
    )

    for item in guest.items.select_related("product", "variant").all():
        existing = user_cart.items.filter(
            product=item.product, variant=item.variant
        ).first()
        if existing:
            new_qty = existing.quantity + item.quantity
            assert_stock(item.product, item.variant, new_qty)
            existing.quantity = new_qty
            existing.save(update_fields=["quantity"])
            item.delete()
        else:
            assert_stock(item.product, item.variant, item.quantity)
            item.cart = user_cart
            item.save(update_fields=["cart"])

    for d in guest.discounts.all():
        CartDiscount.objects.get_or_create(
            cart=user_cart,
            code=d.code,
            defaults={
                "discount_type": d.discount_type,
                "amount": d.amount,
            },
        )

    guest.is_active = False
    guest.save(update_fields=["is_active"])
    return cart_queryset().get(pk=user_cart.pk)


def apply_coupon(cart: Cart, code: str) -> CartDiscount:
    from apps.core.exceptions import DiscountAlreadyApplied, DiscountCodeInvalid
    from apps.promotions.services import coupon_is_live, voucher_for_cart

    code = code.strip().upper()
    if cart.discounts.exists():
        # One active discount per cart — prevents unlimited stacking (F-08).
        raise DiscountAlreadyApplied(
            detail="A discount is already applied to this cart."
        )
    if cart.discounts.filter(code=code).exists():
        raise DiscountAlreadyApplied()
    coupon = Coupon.objects.filter(code__iexact=code).first()
    if coupon is not None:
        if not coupon_is_live(coupon):
            raise DiscountCodeInvalid()
        return CartDiscount.objects.create(
            cart=cart,
            code=coupon.code,
            discount_type=coupon.discount_type,
            amount=coupon.amount,
        )
    voucher = voucher_for_cart(cart, code)
    if voucher is None:
        raise DiscountCodeInvalid()
    return CartDiscount.objects.create(
        cart=cart,
        code=voucher.code,
        discount_type=CartDiscount.DiscountType.FIXED,
        amount=voucher.remaining_amount,
    )
