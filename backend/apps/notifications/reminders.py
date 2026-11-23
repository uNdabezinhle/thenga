"""Paid reminder mail and the monthly operated-ad statement."""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.catalogue.models import Inventory
from apps.notifications.models import NotificationLog
from apps.notifications.services import send_email
from apps.orders.models import Order
from apps.platform.models import Merchant, MerchantMembership
from apps.platform.services import has_addon
from apps.pos.models import DrawerSession
from apps.promotions.ads import close_statement, previous_month


def _already(template: str, **meta) -> bool:
    qs = NotificationLog.objects.filter(template=template)
    for key, value in meta.items():
        qs = qs.filter(**{f"metadata__{key}": value})
    return qs.exists()


def _owner_email(merchant: Merchant) -> str:
    if merchant.support_email:
        return merchant.support_email
    row = (
        MerchantMembership.objects.select_related("user")
        .filter(merchant=merchant, role=MerchantMembership.Role.OWNER)
        .order_by("id")
        .first()
    )
    return row.user.email if row else ""


def remind_unpaid(now) -> int:
    cutoff = now - timedelta(hours=2)
    sent = 0
    orders = Order.objects.filter(
        status=Order.Status.AWAITING_PAYMENT,
        channel=Order.Channel.ONLINE,
        placed_at__lt=cutoff,
    ).prefetch_related("items__product__merchant")
    for order in orders:
        merchants = {
            item.product.merchant
            for item in order.items.all()
            if item.product.merchant_id
        }
        merchant = next(iter(merchants), None)
        if merchant is None or len(merchants) != 1 or not has_addon(merchant, "reminders"):
            continue
        if _already("payment_reminder", order_id=order.id):
            continue
        send_email(
            to=order.user.email,
            subject=f"Finish payment for {order.reference}",
            template="payment_reminder",
            context={"order": order, "reference": order.reference},
            user=order.user,
            merchant=merchant,
            metadata={"order_id": order.id},
        )
        sent += 1
    return sent


def remind_trials(now) -> int:
    sent = 0
    horizon = now + timedelta(days=3)
    rows = Merchant.objects.filter(
        status=Merchant.Status.TRIALING,
        trial_ends__gt=now,
        trial_ends__lte=horizon,
    )
    for merchant in rows:
        if not has_addon(merchant, "reminders"):
            continue
        stamp = merchant.trial_ends.date().isoformat()
        if _already("trial_ending", merchant_id=merchant.id, trial_day=stamp):
            continue
        to = _owner_email(merchant)
        if not to:
            continue
        send_email(
            to=to,
            subject=f"{merchant.trading_name} trial ends soon",
            template="trial_ending",
            context={"trial_ends": merchant.trial_ends.isoformat()},
            merchant=merchant,
            metadata={"merchant_id": merchant.id, "trial_day": stamp},
        )
        sent += 1
    return sent


def remind_low_stock(now) -> int:
    sent = 0
    day = now.date().isoformat()
    threshold = settings.LOW_STOCK_THRESHOLD
    rows = Inventory.objects.select_related("variant__product__merchant").filter(
        variant__product__merchant__isnull=False
    )
    for row in rows:
        available = row.available
        if available <= 0 or available > threshold:
            continue
        merchant = row.variant.product.merchant
        if not has_addon(merchant, "reminders"):
            continue
        if _already("low_stock", variant_id=row.variant_id, day=day):
            continue
        to = _owner_email(merchant)
        if not to:
            continue
        send_email(
            to=to,
            subject=f"Low stock: {row.variant.sku}",
            template="low_stock",
            context={"sku": row.variant.sku, "available": available},
            merchant=merchant,
            metadata={"variant_id": row.variant_id, "day": day},
        )
        sent += 1
    return sent


def remind_open_drawers(now) -> int:
    sent = 0
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = DrawerSession.objects.select_related("store__merchant").filter(
        status=DrawerSession.Status.OPEN,
        opened_at__lt=start,
        store__merchant__isnull=False,
    )
    for session in rows:
        merchant = session.store.merchant
        if not has_addon(merchant, "reminders"):
            continue
        if _already("drawer_open", session_id=session.id):
            continue
        to = _owner_email(merchant)
        if not to:
            continue
        send_email(
            to=to,
            subject=f"Till drawer still open at {session.store.name}",
            template="drawer_open",
            context={"store": session.store.name},
            merchant=merchant,
            metadata={"session_id": session.id},
        )
        sent += 1
    return sent


def send_ad_statements(on, *, force: bool = False) -> int:
    if not force and on.day != 1:
        return 0
    period = previous_month(on)
    sent = 0
    for merchant in Merchant.objects.filter(operated_ads=True):
        row = close_statement(merchant, period)
        if row is None or row.emailed_at:
            continue
        to = _owner_email(merchant)
        if not to:
            continue
        send_email(
            to=to,
            subject=f"Reka Ads statement {period.isoformat()}",
            template="ad_statement",
            context={
                "period": period.isoformat(),
                "clicks": row.clicks,
                "gross": f"{row.gross:.2f}",
                "merchant_share": f"{row.merchant_share:.2f}",
                "reka_fee": f"{row.reka_fee:.2f}",
            },
            merchant=merchant,
            metadata={"period": period.isoformat(), "merchant_id": merchant.id},
        )
        row.emailed_at = timezone.now()
        row.save(update_fields=["emailed_at"])
        sent += 1
    return sent


def run_reminders(now=None, *, statements: bool = False) -> dict:
    now = now or timezone.now()
    return {
        "unpaid": remind_unpaid(now),
        "trials": remind_trials(now),
        "low_stock": remind_low_stock(now),
        "drawers": remind_open_drawers(now),
        "statements": send_ad_statements(now.date(), force=statements),
    }
