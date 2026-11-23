"""Counter sales. One order per idempotency key, same stock rules as the shop."""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.cart.models import Coupon
from apps.catalogue.models import Inventory, Product, ProductVariant
from apps.core.exceptions import CartItemOutOfStock, DiscountAlreadyApplied, DiscountCodeInvalid
from apps.orders.models import Order, OrderEvent, OrderItem, Payment
from apps.orders.serializers import OrderSerializer
from apps.orders.services import OrderError
from apps.pricing.services import Line, compute_totals, money_str
from apps.promotions.models import Bundle, Voucher
from apps.promotions.services import coupon_is_live
from apps.promotions.specials import live_unit_price, split_bundle_prices

from .constants import (
    COUNTER_EMAIL,
    COUNTER_USERNAME,
    DRAWER_PULSE,
    HARBOUR_CODE,
    TRAIL_CODE,
)
from .models import DrawerMovement, DrawerSession, Store, StoreCatalogItem, StoreStock


def ensure_stores():
    harbour, _ = Store.objects.get_or_create(
        code=HARBOUR_CODE,
        defaults={"name": "Harbour", "sells_online": True, "is_active": True},
    )
    trail, _ = Store.objects.get_or_create(
        code=TRAIL_CODE,
        defaults={"name": "Trail shop", "sells_online": False, "is_active": True},
    )
    return harbour, trail


def counter_user() -> User:
    user = User.objects.filter(email__iexact=COUNTER_EMAIL).first()
    if user:
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=["email_verified"])
        return user
    try:
        return User.objects.create_user(
            email=COUNTER_EMAIL,
            username=COUNTER_USERNAME,
            password=None,
            email_verified=True,
        )
    except IntegrityError:
        return User.objects.get(email__iexact=COUNTER_EMAIL)


def _store(code: str | None) -> Store:
    ensure_stores()
    cleaned = (code or HARBOUR_CODE).strip().lower() or HARBOUR_CODE
    store = Store.objects.filter(code=cleaned, is_active=True).first()
    if store is None:
        raise OrderError("That store is not open.", code="store_not_found")
    return store


def _catalog_rows(store):
    return list(
        StoreCatalogItem.objects.filter(store=store).select_related("variant", "bundle")
    )


def _allowed(rows, *, variant_id=None, bundle_id=None) -> bool:
    if not rows:
        return True
    if variant_id is not None:
        return any(row.variant_id == variant_id for row in rows)
    return any(row.bundle_id == bundle_id for row in rows)


def _override(rows, *, variant_id=None, bundle_id=None):
    for row in rows:
        if variant_id is not None and row.variant_id == variant_id:
            return row.price_override
        if bundle_id is not None and row.bundle_id == bundle_id:
            return row.price_override
    return None


def available_units(store, variant) -> int:
    if store.sells_online:
        inv = getattr(variant, "inventory", None)
        if inv is None:
            inv = Inventory.objects.filter(variant=variant).first()
        return inv.available if inv else 0
    row = StoreStock.objects.filter(store=store, variant=variant).first()
    return row.available if row else 0


def _reserve(store, variant_id: int, qty: int, name: str) -> None:
    if store.sells_online:
        try:
            row = Inventory.objects.select_for_update().get(variant_id=variant_id)
        except Inventory.DoesNotExist:
            raise CartItemOutOfStock(
                detail=f"{name} is out of stock.",
                details={"product": name},
            )
    else:
        try:
            row = StoreStock.objects.select_for_update().get(
                store=store, variant_id=variant_id
            )
        except StoreStock.DoesNotExist:
            raise CartItemOutOfStock(
                detail=f"{name} is out of stock.",
                details={"product": name},
            )
    if not row.reserve(qty):
        raise CartItemOutOfStock(
            detail=f"Only {row.available} of {name} are available.",
            details={"available": row.available, "requested": qty, "product": name},
        )


def _qty(raw) -> int:
    try:
        qty = int(raw)
    except (TypeError, ValueError):
        qty = 0
    if qty < 1:
        raise OrderError("Quantity must be at least 1.", code="validation_failed")
    return qty


def _in_scope(variant, scope) -> bool:
    if scope is None:
        return True
    return ProductVariant.objects.filter(pk=variant.pk).filter(scope).exists()


def _expand(store, lines: list, scope=None) -> list[dict]:
    if not isinstance(lines, list) or not lines:
        raise OrderError("Add at least one line.", code="cart_empty")
    rows = _catalog_rows(store)
    expanded = []
    for line in lines:
        if not isinstance(line, dict):
            raise OrderError("Each line needs a variant or a bundle.", code="validation_failed")
        qty = _qty(line.get("quantity"))
        bundle_id = line.get("bundle_id")
        if bundle_id:
            try:
                bundle = Bundle.objects.get(pk=int(bundle_id), is_active=True)
            except (Bundle.DoesNotExist, TypeError, ValueError):
                raise OrderError("That bundle is not on the till.", code="not_found")
            if not _allowed(rows, bundle_id=bundle.pk):
                raise OrderError("That bundle is not in this store.", code="not_in_store")
            components = list(bundle.items.select_related("product", "variant"))
            if not components:
                raise OrderError("That bundle is empty.", code="bundle_locked")
            price = _override(rows, bundle_id=bundle.pk)
            prices = split_bundle_prices(
                [component.quantity for component in components],
                price if price is not None else bundle.price,
            )
            for component, unit in zip(components, prices):
                expanded.append(
                    {
                        "product": component.product,
                        "variant": component.variant,
                        "quantity": component.quantity * qty,
                        "unit_price": unit,
                        "name": f"{bundle.title} · {component.product.name}",
                        "sku": component.variant.sku,
                        "bundle": True,
                    }
                )
            continue
        variant_id = line.get("variant_id")
        if not variant_id:
            raise OrderError("Each line needs a variant or a bundle.", code="validation_failed")
        try:
            variant = ProductVariant.objects.select_related("product", "product__merchant").get(
                pk=int(variant_id), is_active=True, product__is_active=True
            )
        except (ProductVariant.DoesNotExist, TypeError, ValueError):
            raise OrderError("That product is not on the till.", code="not_found")
        if not _in_scope(variant, scope):
            raise OrderError("That product is not on this till.", code="not_found")
        if variant.product.sale_channel == Product.SaleChannel.ONLINE:
            raise OrderError("That product is not sold at the till.", code="not_on_till")
        if not _allowed(rows, variant_id=variant.pk):
            raise OrderError("That product is not in this store.", code="not_in_store")
        override = _override(rows, variant_id=variant.pk)
        expanded.append(
            {
                "product": variant.product,
                "variant": variant,
                "quantity": qty,
                "unit_price": override if override is not None else live_unit_price(variant.product, variant),
                "name": variant.product.name,
                "sku": variant.sku,
                "bundle": False,
            }
        )
    return expanded


def _customer(email: str | None):
    cleaned = (email or "").strip()
    if not cleaned:
        return counter_user()
    user = User.objects.filter(email__iexact=cleaned).first()
    if user is None:
        raise OrderError("No customer with that email.", code="customer_not_found")
    return user


def _discount(user, code: str, subtotal: Decimal, has_bundle: bool):
    cleaned = (code or "").strip()
    if not cleaned:
        return Decimal("0.00"), ""
    if has_bundle:
        raise DiscountAlreadyApplied(detail="Remove the bundle before using a code.")
    coupon = Coupon.objects.filter(code__iexact=cleaned).first()
    if coupon is not None:
        if not coupon_is_live(coupon):
            raise DiscountCodeInvalid()
        totals = compute_totals(
            lines=[Line(unit_price=subtotal, quantity=1)],
            discounts=[(coupon.discount_type, coupon.amount)],
        )
        return totals.discount_total, coupon.code
    voucher = (
        Voucher.objects.filter(
            code__iexact=cleaned,
            owner=user,
            redeemed_order__isnull=True,
        )
        .exclude(remaining_amount__lte=0)
        .first()
    )
    if voucher is None or (voucher.expires_at and voucher.expires_at < timezone.now()):
        raise DiscountCodeInvalid()
    totals = compute_totals(
        lines=[Line(unit_price=subtotal, quantity=1)],
        discounts=[("fixed", voucher.remaining_amount)],
    )
    return totals.discount_total, voucher.code


def _new_reference() -> str:
    ref = Order.generate_reference()
    while Order.objects.filter(reference=ref).exists():
        ref = Order.generate_reference()
    return ref


def _pending_redirect(order: Order) -> str:
    if order.payment_method != "payfast" or order.status != Order.Status.AWAITING_PAYMENT:
        return ""
    payment = order.payments.filter(status=Payment.Status.PENDING).order_by("-id").first()
    if payment is None:
        return ""
    from django.conf import settings

    base = getattr(settings, "PUBLIC_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    if payment.provider == "payfast":
        return f"{base}/api/v1/payments/payfast/redirect/?order={order.reference}"
    return (
        f"{base}/api/v1/payments/sandbox/checkout/"
        f"?ref={payment.provider_reference}&order={order.reference}"
        f"&amount={order.grand_total:.2f}&currency={order.currency}"
    )


def sale_body(order: Order, *, replayed: bool = False) -> dict:
    paid = order.status == Order.Status.PAYMENT_CONFIRMED
    redirect = _pending_redirect(order)
    kick = (not replayed) and paid and order.payment_method == "cash"
    payload = OrderSerializer(order).data
    return {
        "order": payload,
        "reference": order.reference,
        "status": order.status,
        "grand_total": money_str(order.grand_total),
        "receipt_url": f"/api/v1/orders/{order.reference}/invoice/" if paid else "",
        "redirect_url": redirect,
        "awaiting_payment": order.status == Order.Status.AWAITING_PAYMENT,
        "drawer_kick": kick,
        "drawer_pulse": DRAWER_PULSE if kick else "",
        "replayed": replayed,
    }


def _pay_now(order: Order, tender: str) -> None:
    payment = Payment.objects.create(
        order=order,
        provider=f"pos_{tender}",
        provider_reference=f"POS-{uuid.uuid4().hex[:12].upper()}",
        status=Payment.Status.PENDING,
        amount=order.grand_total,
        currency=order.currency,
        idempotency_key=f"pay-{order.idempotency_key}",
    )
    from apps.payments.services import confirm_payment_from_webhook

    confirm_payment_from_webhook(
        provider_reference=payment.provider_reference,
        status="succeeded",
        amount=payment.amount,
    )


def _payfast(order: Order) -> str:
    from apps.payments.providers import PayfastProvider

    session = PayfastProvider().create_checkout(
        order_reference=order.reference,
        amount=order.grand_total,
        currency=order.currency,
        return_url="",
        cancel_url="",
        idempotency_key=order.idempotency_key or order.reference,
    )
    Payment.objects.create(
        order=order,
        provider=session.provider,
        provider_reference=session.provider_reference,
        status=Payment.Status.PENDING,
        amount=order.grand_total,
        currency=order.currency,
        idempotency_key=f"pay-{order.idempotency_key}",
    )
    return session.redirect_url or ""


def _record_cash(order: Order, staff) -> None:
    session = (
        DrawerSession.objects.select_for_update()
        .filter(store_id=order.store_id, status=DrawerSession.Status.OPEN)
        .order_by("-id")
        .first()
    )
    if session is None:
        session = DrawerSession.objects.create(
            store_id=order.store_id,
            opened_by=staff,
            opening_float=Decimal("0.00"),
            status=DrawerSession.Status.OPEN,
        )
    DrawerMovement.objects.create(
        session=session,
        kind=DrawerMovement.Kind.SALE,
        amount=order.grand_total,
        order=order,
    )


@transaction.atomic
def create_pos_sale(*, staff, payload: dict) -> dict:
    from apps.platform.services import merchant_for, require_feature

    require_feature(merchant_for(staff), "pos")
    key = str((payload or {}).get("idempotency_key") or "").strip()
    if not key:
        raise OrderError("Send an idempotency key.", code="idempotency_required")
    if len(key) > 64:
        raise OrderError("That idempotency key is too long.", code="validation_failed")
    existing = (
        Order.objects.filter(idempotency_key=key)
        .prefetch_related("items", "events", "shipments__events", "payments")
        .first()
    )
    if existing:
        return sale_body(existing, replayed=True)

    tender = str(payload.get("tender") or "cash").strip().lower()
    if tender not in ("cash", "card", "payfast"):
        raise OrderError("Tender must be cash, card, or payfast.", code="validation_failed")
    store = _store(payload.get("store_code"))
    buyer = _customer(payload.get("customer_email"))
    from apps.platform.services import variant_scope

    expanded = _expand(store, payload.get("lines") or [], variant_scope(staff))
    has_bundle = any(line["bundle"] for line in expanded)
    subtotal = sum(
        (line["unit_price"] * line["quantity"] for line in expanded),
        Decimal("0.00"),
    )
    discount, code = _discount(buyer, payload.get("discount_code") or "", subtotal, has_bundle)
    totals = compute_totals(
        lines=[Line(unit_price=line["unit_price"], quantity=line["quantity"]) for line in expanded],
        discounts=[("fixed", discount)] if discount else [],
    )
    for line in expanded:
        _reserve(store, line["variant"].pk, line["quantity"], line["name"])

    order = Order.objects.create(
        reference=_new_reference(),
        user=buyer,
        store=store,
        channel=Order.Channel.POS,
        shipping_address_text="Collected in store",
        status=Order.Status.AWAITING_PAYMENT,
        currency=totals.currency,
        subtotal=totals.subtotal,
        discount_total=totals.discount_total,
        shipping_total=Decimal("0.00"),
        tax_total=Decimal("0.00"),
        grand_total=totals.grand_total,
        shipping_method="",
        payment_method=tender,
        discount_code=code,
        idempotency_key=key,
    )
    for line in expanded:
        OrderItem.objects.create(
            order=order,
            product=line["product"],
            variant=line["variant"],
            product_name_snapshot=line["name"],
            sku_snapshot=line["sku"],
            unit_price=line["unit_price"],
            quantity=line["quantity"],
            line_total=line["unit_price"] * line["quantity"],
        )
    OrderEvent.objects.create(
        order=order,
        from_status="",
        to_status=Order.Status.AWAITING_PAYMENT,
        actor=staff,
        note="Counter sale",
    )
    if tender == "payfast":
        _payfast(order)
    else:
        _pay_now(order, tender)
        order.refresh_from_db()
        if tender == "cash":
            _record_cash(order, staff)
    order = Order.objects.prefetch_related(
        "items", "events", "shipments__events", "payments"
    ).get(pk=order.pk)
    return sale_body(order, replayed=False)


def sell(staff, payload: dict) -> dict:
    key = str((payload or {}).get("idempotency_key") or "").strip()
    try:
        return create_pos_sale(staff=staff, payload=payload)
    except IntegrityError:
        existing = Order.objects.filter(idempotency_key=key).first()
        if existing is None:
            raise
        return sale_body(existing, replayed=True)


def sync_sales(staff, sales: list) -> list[dict]:
    results = []
    if not isinstance(sales, list):
        raise OrderError("Send a list of sales.", code="validation_failed")
    for payload in sales:
        key = ""
        if isinstance(payload, dict):
            key = str(payload.get("idempotency_key") or "")
        try:
            body = sell(staff, payload if isinstance(payload, dict) else {})
            results.append(
                {
                    "idempotency_key": key,
                    "ok": True,
                    "reference": body["reference"],
                    "status": body["status"],
                    "grand_total": body["grand_total"],
                    "replayed": body["replayed"],
                    "error": None,
                }
            )
        except (OrderError, CartItemOutOfStock, DiscountCodeInvalid, DiscountAlreadyApplied) as exc:
            results.append(
                {
                    "idempotency_key": key,
                    "ok": False,
                    "reference": "",
                    "status": "",
                    "grand_total": "",
                    "replayed": False,
                    "error": {"code": exc.default_code, "message": str(exc.detail)},
                }
            )
    return results


def open_drawer(staff, *, store_code: str | None, opening_float) -> DrawerSession:
    store = _store(store_code)
    current = (
        DrawerSession.objects.filter(store=store, status=DrawerSession.Status.OPEN)
        .order_by("-id")
        .first()
    )
    if current:
        return current
    try:
        float_amount = Decimal(str(opening_float if opening_float not in (None, "") else "0"))
    except Exception:
        raise OrderError("Opening float must be a number.", code="validation_failed")
    if float_amount < 0:
        raise OrderError("Opening float cannot be negative.", code="validation_failed")
    return DrawerSession.objects.create(
        store=store,
        opened_by=staff,
        opening_float=float_amount,
        status=DrawerSession.Status.OPEN,
    )


def expected_cash(session: DrawerSession) -> Decimal:
    total = session.opening_float
    for movement in session.movements.all():
        if movement.kind == DrawerMovement.Kind.PAY_OUT:
            total -= movement.amount
        else:
            total += movement.amount
    return total


@transaction.atomic
def close_drawer(staff, *, store_code: str | None, closing_count) -> DrawerSession:
    store = _store(store_code)
    session = (
        DrawerSession.objects.select_for_update()
        .filter(store=store, status=DrawerSession.Status.OPEN)
        .order_by("-id")
        .first()
    )
    if session is None:
        raise OrderError("No drawer is open.", code="drawer_closed")
    try:
        counted = Decimal(str(closing_count))
    except Exception:
        raise OrderError("Enter the counted cash.", code="validation_failed")
    session.expected = expected_cash(session)
    session.closing_count = counted
    session.status = DrawerSession.Status.CLOSED
    session.closed_at = timezone.now()
    session.save(update_fields=["expected", "closing_count", "status", "closed_at"])
    return session


def move_drawer(staff, *, store_code: str | None, kind: str, amount, note: str = "") -> DrawerMovement:
    if kind not in (DrawerMovement.Kind.PAY_IN, DrawerMovement.Kind.PAY_OUT):
        raise OrderError("Movement must be pay_in or pay_out.", code="validation_failed")
    session = open_drawer(staff, store_code=store_code, opening_float="0")
    try:
        value = Decimal(str(amount))
    except Exception:
        raise OrderError("Amount must be a number.", code="validation_failed")
    if value <= 0:
        raise OrderError("Amount must be greater than zero.", code="validation_failed")
    return DrawerMovement.objects.create(
        session=session, kind=kind, amount=value, note=(note or "")[:255]
    )


def drawer_state(store_code: str | None) -> dict:
    store = _store(store_code)
    session = (
        DrawerSession.objects.filter(store=store, status=DrawerSession.Status.OPEN)
        .order_by("-id")
        .first()
    )
    if session is None:
        return {"store": store.code, "open": False, "expected": None, "opening_float": None}
    return {
        "store": store.code,
        "open": True,
        "opening_float": money_str(session.opening_float),
        "expected": money_str(expected_cash(session)),
        "session_id": session.pk,
    }
