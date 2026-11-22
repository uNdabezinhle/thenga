"""Daily payment reconciliation — REKA-FR-PAY-007 (Should)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.orders.models import Order, Payment, Refund
from apps.pricing.services import money_str, q


@dataclass
class ReconciliationReport:
    date: str
    payments_succeeded: int
    payments_failed: int
    payments_pending: int
    gross_captured: Decimal
    gross_refunded: Decimal
    net: Decimal
    order_count_paid: int
    exceptions: list[dict]

    def as_dict(self) -> dict:
        return {
            "date": self.date,
            "payments_succeeded": self.payments_succeeded,
            "payments_failed": self.payments_failed,
            "payments_pending": self.payments_pending,
            "gross_captured": money_str(self.gross_captured),
            "gross_refunded": money_str(self.gross_refunded),
            "net": money_str(self.net),
            "currency": "ZAR",
            "order_count_paid": self.order_count_paid,
            "exceptions": self.exceptions,
            "exception_count": len(self.exceptions),
        }


def _day_bounds(day: date):
    start = timezone.make_aware(datetime.combine(day, time.min))
    end = start + timedelta(days=1)
    return start, end


def build_reconciliation(day: date | None = None) -> ReconciliationReport:
    """Summarise payments/refunds for a calendar day (UTC) and flag mismatches."""
    day = day or timezone.now().date()
    start, end = _day_bounds(day)

    payments = Payment.objects.filter(created_at__gte=start, created_at__lt=end)
    succeeded = payments.filter(
        status__in=(
            Payment.Status.SUCCEEDED,
            Payment.Status.PARTIALLY_REFUNDED,
            Payment.Status.REFUNDED,
        )
    )
    failed = payments.filter(status=Payment.Status.FAILED)
    pending = payments.filter(status=Payment.Status.PENDING)

    gross = succeeded.aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
    refunds = Refund.objects.filter(created_at__gte=start, created_at__lt=end)
    refunded = refunds.aggregate(s=Sum("amount"))["s"] or Decimal("0.00")

    paid_orders = Order.objects.filter(
        placed_at__gte=start,
        placed_at__lt=end,
        status__in=(
            Order.Status.PAYMENT_CONFIRMED,
            Order.Status.PACKED,
            Order.Status.OUT_FOR_DELIVERY,
            Order.Status.DELIVERED,
            Order.Status.REFUNDED,
        ),
    ).count()

    exceptions: list[dict] = []

    # Paid order without succeeded payment
    for order in Order.objects.filter(
        placed_at__gte=start,
        placed_at__lt=end,
        status=Order.Status.PAYMENT_CONFIRMED,
    ).prefetch_related("payments"):
        ok = order.payments.filter(
            status__in=(
                Payment.Status.SUCCEEDED,
                Payment.Status.PARTIALLY_REFUNDED,
                Payment.Status.REFUNDED,
            )
        ).exists()
        if not ok:
            exceptions.append(
                {
                    "type": "order_paid_without_payment",
                    "order_reference": order.reference,
                    "message": "Order is payment_confirmed but has no succeeded payment row.",
                }
            )

    # Pending payments older than 2 hours (abandoned checkout)
    stale_cutoff = timezone.now() - timedelta(hours=2)
    for p in Payment.objects.filter(
        status=Payment.Status.PENDING, created_at__lt=stale_cutoff
    ).select_related("order")[:50]:
        exceptions.append(
            {
                "type": "stale_pending_payment",
                "order_reference": p.order.reference,
                "provider_reference": p.provider_reference,
                "message": "Payment still pending after 2 hours.",
            }
        )

    # Amount mismatch: order grand_total vs payment amount
    for p in succeeded.select_related("order"):
        if q(p.amount) != q(p.order.grand_total):
            exceptions.append(
                {
                    "type": "amount_mismatch",
                    "order_reference": p.order.reference,
                    "payment_amount": money_str(p.amount),
                    "order_total": money_str(p.order.grand_total),
                    "message": "Payment amount does not match order grand_total.",
                }
            )

    return ReconciliationReport(
        date=day.isoformat(),
        payments_succeeded=succeeded.count(),
        payments_failed=failed.count(),
        payments_pending=pending.count(),
        gross_captured=q(gross),
        gross_refunded=q(refunded),
        net=q(gross - refunded),
        order_count_paid=paid_orders,
        exceptions=exceptions,
    )
