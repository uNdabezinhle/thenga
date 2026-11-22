"""Background payment maintenance tasks."""
from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="payments.release_stale_pending")
def release_stale_pending_payments(hours: int = 2) -> dict:
    """
    Cancel orders still awaiting payment after `hours` and release reserved stock.

    Abandoned checkouts leave inventory reserved; this frees it for other shoppers.
    """
    from apps.catalogue.models import Inventory
    from apps.orders.models import Order, OrderEvent, Payment
    from apps.orders.services import transition_order

    cutoff = timezone.now() - timedelta(hours=hours)
    pending = (
        Payment.objects.filter(
            status=Payment.Status.PENDING,
            created_at__lt=cutoff,
            order__status=Order.Status.AWAITING_PAYMENT,
        )
        .select_related("order")
        .prefetch_related("order__items")
    )

    cancelled = 0
    released_units = 0
    for payment in pending:
        order = payment.order
        with transaction.atomic():
            # Re-fetch under lock
            order = Order.objects.select_for_update().get(pk=order.pk)
            if order.status != Order.Status.AWAITING_PAYMENT:
                continue
            payment = Payment.objects.select_for_update().get(pk=payment.pk)
            if payment.status != Payment.Status.PENDING:
                continue

            for item in order.items.select_related("variant").all():
                if not item.variant_id:
                    continue
                try:
                    inv = Inventory.objects.select_for_update().get(
                        variant_id=item.variant_id
                    )
                except Inventory.DoesNotExist:
                    continue
                before = inv.reserved_quantity
                inv.release(item.quantity)
                released_units += max(0, before - inv.reserved_quantity)

            payment.status = Payment.Status.FAILED
            payment.save(update_fields=["status"])
            transition_order(
                order,
                Order.Status.CANCELLED,
                actor=None,
                note=f"Auto-cancelled: payment pending >{hours}h (abandoned checkout)",
            )
            cancelled += 1

    logger.info(
        "release_stale_pending cancelled=%s released_units=%s",
        cancelled,
        released_units,
    )
    return {"cancelled_orders": cancelled, "released_units": released_units}


@shared_task(name="payments.run_daily_reconciliation")
def run_daily_reconciliation() -> dict:
    """Log yesterday's reconciliation summary (hook for email/Slack later)."""
    from datetime import timedelta

    from .reconciliation import build_reconciliation

    day = (timezone.now() - timedelta(days=1)).date()
    report = build_reconciliation(day)
    logger.info(
        "reconciliation date=%s captured=%s refunded=%s exceptions=%s",
        report.date,
        report.gross_captured,
        report.gross_refunded,
        len(report.exceptions),
    )
    return report.as_dict()
