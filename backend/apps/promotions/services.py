"""Spend and restore the single cart code when an order is paid or cancelled."""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.cart.models import Coupon
from apps.promotions.models import Voucher


def coupon_is_live(coupon: Coupon, now=None) -> bool:
    now = now or timezone.now()
    if not coupon.is_active:
        return False
    if coupon.starts_at and coupon.starts_at > now:
        return False
    if coupon.ends_at and coupon.ends_at < now:
        return False
    if coupon.max_uses is not None and coupon.times_used >= coupon.max_uses:
        return False
    return True


def voucher_for_cart(cart, code: str):
    if cart.user_id is None:
        return None
    voucher = (
        Voucher.objects.filter(code__iexact=code, owner_id=cart.user_id)
        .exclude(remaining_amount__lte=0)
        .filter(redeemed_order__isnull=True)
        .first()
    )
    if voucher is None:
        return None
    if voucher.expires_at and voucher.expires_at < timezone.now():
        return None
    return voucher


@transaction.atomic
def settle_order_discount(order) -> None:
    if not order.discount_code or order.discount_settled:
        return
    code = order.discount_code
    voucher = (
        Voucher.objects.select_for_update()
        .filter(code__iexact=code, owner_id=order.user_id, redeemed_order__isnull=True)
        .first()
    )
    if voucher and voucher.remaining_amount > 0:
        voucher.remaining_amount = Decimal("0")
        voucher.redeemed_order = order
        voucher.save(update_fields=["remaining_amount", "redeemed_order"])
    coupon = Coupon.objects.select_for_update().filter(code__iexact=code).first()
    if coupon:
        coupon.times_used += 1
        coupon.save(update_fields=["times_used"])
    order.discount_settled = True
    order.save(update_fields=["discount_settled"])


@transaction.atomic
def restore_order_discount(order) -> None:
    if not order.discount_settled or not order.discount_code:
        return
    voucher = (
        Voucher.objects.select_for_update().filter(redeemed_order=order).first()
    )
    if voucher:
        voucher.remaining_amount = voucher.amount
        voucher.redeemed_order = None
        voucher.save(update_fields=["remaining_amount", "redeemed_order"])
    coupon = Coupon.objects.select_for_update().filter(code__iexact=order.discount_code).first()
    if coupon and coupon.times_used > 0:
        coupon.times_used -= 1
        coupon.save(update_fields=["times_used"])
    order.discount_settled = False
    order.save(update_fields=["discount_settled"])
