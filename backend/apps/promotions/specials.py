"""Flash prices, bundles, loyalty points, and referrals."""
from __future__ import annotations

import re
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.cart.models import Cart, CartItem
from apps.catalogue.models import FlashPrice
from apps.core.exceptions import BundleLocked, DiscountAlreadyApplied
from apps.orders.models import Order
from apps.promotions.models import Bundle, LoyaltyAccount, ReferralProfile, Voucher

REDEEM_POINTS = 100
REDEEM_RAND = Decimal("10.00")
REFERRAL_POINTS = 50
REFERRAL_RAND = Decimal("20.00")
PAID_STATUSES = (
    Order.Status.PAYMENT_CONFIRMED,
    Order.Status.PACKED,
    Order.Status.OUT_FOR_DELIVERY,
    Order.Status.DELIVERED,
)


def flash_for(product, now=None):
    now = now or timezone.now()
    row = (
        FlashPrice.objects.filter(product_id=product.pk, is_active=True)
        .order_by("-id")
        .first()
    )
    if row is None:
        return None
    if row.starts_at and row.starts_at > now:
        return None
    if row.ends_at and row.ends_at < now:
        return None
    return row


def live_unit_price(product, variant=None) -> Decimal:
    flash = flash_for(product)
    base = flash.sale_price if flash else product.base_price
    delta = variant.price_delta if variant is not None else Decimal("0.00")
    return base + delta


def ensure_referral(user) -> ReferralProfile:
    profile = ReferralProfile.objects.filter(user=user).first()
    if profile:
        return profile
    base = re.sub(r"[^A-Z0-9]", "", (user.username or "TRAIL").upper())[:8] or "TRAIL"
    code = base
    suffix = 2
    while ReferralProfile.objects.filter(code=code).exists():
        code = f"{base[:12]}{suffix}"
        suffix += 1
    return ReferralProfile.objects.create(user=user, code=code)


def loyalty_account(user) -> LoyaltyAccount:
    account, _ = LoyaltyAccount.objects.get_or_create(user=user)
    return account


def _paid_before(order) -> bool:
    return (
        Order.objects.filter(user_id=order.user_id, status__in=PAID_STATUSES)
        .exclude(pk=order.pk)
        .exists()
    )


def _voucher_code(prefix: str) -> str:
    while True:
        code = f"{prefix}{uuid.uuid4().hex[:8].upper()}"
        if not Voucher.objects.filter(code=code).exists():
            return code


@transaction.atomic
def award_order_specials(order) -> None:
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.specials_awarded:
        return
    points = int(order.subtotal // Decimal("10"))
    account = LoyaltyAccount.objects.select_for_update().get_or_create(user_id=order.user_id)[0]
    account.points += points
    account.save(update_fields=["points"])
    order.loyalty_points = points
    order.specials_awarded = True
    order.save(update_fields=["loyalty_points", "specials_awarded"])

    profile = ReferralProfile.objects.select_for_update().filter(user_id=order.user_id).first()
    if profile is None or profile.referrer_id is None or profile.settled:
        return
    if _paid_before(order):
        return
    voucher = Voucher.objects.create(
        code=_voucher_code("REF"),
        owner_id=order.user_id,
        amount=REFERRAL_RAND,
        remaining_amount=REFERRAL_RAND,
    )
    referrer = LoyaltyAccount.objects.select_for_update().get_or_create(
        user_id=profile.referrer_id
    )[0]
    referrer.points += REFERRAL_POINTS
    referrer.save(update_fields=["points"])
    profile.settled = True
    profile.rewarded_order = order
    profile.reward_voucher = voucher
    profile.referrer_points = REFERRAL_POINTS
    profile.save(
        update_fields=["settled", "rewarded_order", "reward_voucher", "referrer_points"]
    )


@transaction.atomic
def reverse_order_specials(order) -> None:
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.specials_awarded:
        if order.loyalty_points:
            account = LoyaltyAccount.objects.select_for_update().get_or_create(user_id=order.user_id)[0]
            account.points = max(0, account.points - order.loyalty_points)
            account.save(update_fields=["points"])
        order.loyalty_points = 0
        order.specials_awarded = False
        order.save(update_fields=["loyalty_points", "specials_awarded"])

    profile = (
        ReferralProfile.objects.select_for_update()
        .filter(rewarded_order_id=order.pk)
        .first()
    )
    if profile is None:
        return
    if profile.referrer_id and profile.referrer_points:
        referrer = LoyaltyAccount.objects.select_for_update().get_or_create(
            user_id=profile.referrer_id
        )[0]
        referrer.points = max(0, referrer.points - profile.referrer_points)
        referrer.save(update_fields=["points"])
    voucher = profile.reward_voucher
    unspent = (
        voucher is not None
        and voucher.redeemed_order_id is None
        and voucher.remaining_amount == voucher.amount
    )
    profile.referrer_points = 0
    profile.rewarded_order = None
    if unspent:
        voucher.delete()
        profile.reward_voucher = None
        profile.settled = False
    profile.save(
        update_fields=["referrer_points", "rewarded_order", "reward_voucher", "settled"]
    )


@transaction.atomic
def redeem_points(user) -> Voucher:
    account = LoyaltyAccount.objects.select_for_update().get_or_create(user=user)[0]
    if account.points < REDEEM_POINTS:
        raise BundleLocked("You need 100 points to redeem R10.")
    account.points -= REDEEM_POINTS
    account.save(update_fields=["points"])
    return Voucher.objects.create(
        code=_voucher_code("PTS"),
        owner=user,
        amount=REDEEM_RAND,
        remaining_amount=REDEEM_RAND,
    )


def attach_referrer(user, code: str) -> ReferralProfile:
    cleaned = (code or "").strip().upper()
    if not cleaned:
        raise BundleLocked("Enter a referral code.")
    profile = ensure_referral(user)
    if profile.user_id and profile.referrer_id:
        raise BundleLocked("A referral code is already saved.")
    if profile.settled or _user_has_paid(user):
        raise BundleLocked("Referral codes can only be added before your first paid order.")
    match = ReferralProfile.objects.filter(code__iexact=cleaned).exclude(user=user).first()
    own = ReferralProfile.objects.filter(code__iexact=cleaned, user=user).first()
    if own is not None:
        raise BundleLocked("You cannot use your own code.")
    if match is None:
        raise BundleLocked("That referral code is not valid.")
    profile.referrer = match.user
    profile.save(update_fields=["referrer"])
    return profile


def _user_has_paid(user) -> bool:
    return Order.objects.filter(user=user, status__in=PAID_STATUSES).exists()


def split_bundle_prices(quantities: list[int], total: Decimal) -> list[Decimal]:
    cents = int((total * 100).to_integral_value())
    units = sum(quantities)
    if units <= 0:
        raise BundleLocked("This bundle is empty.")
    base = cents // units
    spent = 0
    prices = []
    for index, qty in enumerate(quantities):
        if index == len(quantities) - 1:
            line_cents = cents - spent
        else:
            line_cents = base * qty
            spent += line_cents
        prices.append((Decimal(line_cents) / Decimal(qty) / Decimal("100")).quantize(Decimal("0.01")))
    return prices


@transaction.atomic
def add_bundle_to_cart(cart: Cart, bundle: Bundle) -> Cart:
    if not bundle.is_active:
        raise BundleLocked("That bundle is not available.")
    if cart.discounts.exists():
        raise DiscountAlreadyApplied(detail="Remove the code before adding a bundle.")
    if cart.items.filter(bundle__isnull=False).exists():
        raise BundleLocked("This cart already has a bundle.")
    components = list(bundle.items.select_related("product", "variant", "variant__inventory"))
    if not components:
        raise BundleLocked("This bundle is empty.")
    for component in components:
        if cart.items.filter(product=component.product, variant=component.variant).exists():
            raise BundleLocked("Those products are already in the cart.")
        from apps.cart.services import assert_stock

        assert_stock(component.product, component.variant, component.quantity)
    prices = split_bundle_prices([row.quantity for row in components], bundle.price)
    for component, price in zip(components, prices):
        CartItem.objects.create(
            cart=cart,
            product=component.product,
            variant=component.variant,
            quantity=component.quantity,
            unit_price_snapshot=price,
            bundle=bundle,
        )
    return cart
