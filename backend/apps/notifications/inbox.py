"""Customer-visible inbox. Order rows are always written. Marketing rows need consent."""
from __future__ import annotations

from django.utils import timezone

from .models import InAppNotification
from .services import get_or_create_prefs


def record_order_notice(order) -> InAppNotification:
    brand_status = order.status.replace("_", " ")
    titles = {
        "payment_confirmed": "Payment confirmed",
        "packed": "Order packed",
        "out_for_delivery": "Out for delivery",
        "delivered": "Delivered",
        "cancelled": "Order cancelled",
        "refunded": "Refund processed",
    }
    title = titles.get(order.status, "Order update")
    return InAppNotification.objects.create(
        user=order.user,
        title=title,
        body=f"Order {order.reference} is now {brand_status}.",
        kind=InAppNotification.Kind.ORDER,
    )


def record_marketing_notice(user, title: str, body: str) -> InAppNotification | None:
    prefs = get_or_create_prefs(user)
    if not (prefs.email_marketing or prefs.push_marketing):
        return None
    existing = InAppNotification.objects.filter(
        user=user, kind=InAppNotification.Kind.PROMOTION, title=title
    ).first()
    if existing:
        return existing
    return InAppNotification.objects.create(
        user=user,
        title=title,
        body=body,
        kind=InAppNotification.Kind.PROMOTION,
    )


def mark_read(note: InAppNotification) -> InAppNotification:
    if note.read_at is None:
        note.read_at = timezone.now()
        note.save(update_fields=["read_at"])
    return note
