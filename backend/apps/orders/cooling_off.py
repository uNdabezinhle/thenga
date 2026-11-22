"""ECTA s44 cooling-off (7 days) — REKA-FR-ORD-011 / REKA-NFR-CMP-005."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import RekaAPIException
from apps.orders.models import Order, OrderEvent, Payment
from apps.payments.refunds import issue_refund


COOLING_OFF_DAYS = 7


class CoolingOffError(RekaAPIException):
    status_code = 400
    default_code = "cooling_off_unavailable"


@dataclass
class CoolingOffStatus:
    eligible: bool
    reason: str | None
    deadline: str | None
    days_remaining: int | None
    excluded_items: list[str]


def _payment_confirmed_at(order: Order):
    """When payment was confirmed (event log), else placed_at for COD-like flows."""
    event = (
        order.events.filter(to_status=Order.Status.PAYMENT_CONFIRMED)
        .order_by("created_at")
        .first()
    )
    if event:
        return event.created_at
    if order.status != Order.Status.AWAITING_PAYMENT:
        return order.placed_at
    return None


def cooling_off_status(order: Order) -> CoolingOffStatus:
    if order.status in (
        Order.Status.CANCELLED,
        Order.Status.REFUNDED,
        Order.Status.AWAITING_PAYMENT,
    ):
        return CoolingOffStatus(
            eligible=False,
            reason="Order is not in a state that can exercise cooling-off.",
            deadline=None,
            days_remaining=None,
            excluded_items=[],
        )

    # Already fully refunded via payment status
    paid = order.payments.filter(
        status__in=(
            Payment.Status.SUCCEEDED,
            Payment.Status.PARTIALLY_REFUNDED,
            Payment.Status.REFUNDED,
        )
    ).first()
    if paid and paid.status == Payment.Status.REFUNDED:
        return CoolingOffStatus(
            False, "Order has already been fully refunded.", None, None, []
        )

    confirmed_at = _payment_confirmed_at(order)
    if not confirmed_at:
        return CoolingOffStatus(
            False, "Payment has not been confirmed yet.", None, None, []
        )

    deadline = confirmed_at + timedelta(days=COOLING_OFF_DAYS)
    now = timezone.now()
    if now > deadline:
        return CoolingOffStatus(
            eligible=False,
            reason=f"The {COOLING_OFF_DAYS}-day cooling-off period has ended.",
            deadline=deadline.isoformat().replace("+00:00", "Z"),
            days_remaining=0,
            excluded_items=[],
        )

    # s42(2): if any line is excluded, whole order is ineligible for electronic cooling-off
    # (conservative: merchant may still accept a return under store policy)
    excluded = []
    for item in order.items.select_related("product").all():
        product = item.product
        if product is not None and getattr(product, "cooling_off_excluded", False):
            excluded.append(item.product_name_snapshot or product.name)

    if excluded:
        return CoolingOffStatus(
            eligible=False,
            reason=(
                "One or more items are excluded from the statutory cooling-off right "
                "(ECTA s42(2)). Contact support for a return under store policy."
            ),
            deadline=deadline.isoformat().replace("+00:00", "Z"),
            days_remaining=max(0, (deadline - now).days),
            excluded_items=excluded,
        )

    remaining = (deadline - now).days
    return CoolingOffStatus(
        eligible=True,
        reason=None,
        deadline=deadline.isoformat().replace("+00:00", "Z"),
        days_remaining=remaining,
        excluded_items=[],
    )


@transaction.atomic
def exercise_cooling_off(order: Order, *, user, reason: str = "") -> Order:
    """Customer exercises s44 right: full refund + order marked refunded."""
    if order.user_id != user.id and not user.is_staff:
        raise CoolingOffError("Order not found.", code="not_found")

    status = cooling_off_status(order)
    if not status.eligible:
        raise CoolingOffError(
            status.reason or "Cooling-off is not available.",
            code="cooling_off_unavailable",
            details={
                "deadline": status.deadline,
                "excluded_items": status.excluded_items,
            },
        )

    note = reason.strip() or "Customer exercised ECTA s44 cooling-off right"
    OrderEvent.objects.create(
        order=order,
        from_status=order.status,
        to_status=order.status,
        actor=user,
        note=f"Cooling-off requested: {note}",
    )

    # Full remaining refund through provider path
    issue_refund(
        order=order,
        amount=None,
        reason=f"ECTA s44 cooling-off: {note}"[:255],
        staff_user=user,
        idempotency_key=f"cooling-off-{order.reference}",
    )
    order.refresh_from_db()
    return order
