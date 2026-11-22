"""Staff refunds through the payment provider — REKA-FR-PAY-006."""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.core.exceptions import RekaAPIException
from apps.orders.models import Order, Payment, Refund
from apps.orders.services import transition_order
from apps.pricing.services import q


class RefundError(RekaAPIException):
    status_code = 400
    default_code = "refund_error"


def _provider_refund(payment: Payment, amount: Decimal) -> str:
    """Call provider; sandbox returns a synthetic reference. No card data."""
    if payment.provider in ("sandbox", "cod"):
        return f"RFND-{uuid.uuid4().hex[:12].upper()}"
    # Future: Yoco/Payfast/Peach client here
    raise RefundError(
        f"Refunds not configured for provider {payment.provider}.",
        code="provider_unsupported",
    )


@transaction.atomic
def issue_refund(
    *,
    order: Order,
    amount: Decimal | None = None,
    reason: str = "",
    staff_user=None,
    idempotency_key: str | None = None,
) -> Refund:
    """Full or partial refund. Idempotent on idempotency_key."""
    if idempotency_key:
        existing = Refund.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    if order.status in (Order.Status.CANCELLED, Order.Status.AWAITING_PAYMENT):
        raise RefundError(
            "This order cannot be refunded in its current state.",
            code="order_not_refundable",
        )

    payment = (
        order.payments.select_for_update()
        .filter(
            status__in=(
                Payment.Status.SUCCEEDED,
                Payment.Status.PARTIALLY_REFUNDED,
            )
        )
        .order_by("-created_at")
        .first()
    )
    if not payment:
        raise RefundError("No refundable payment on this order.", code="no_payment")

    already = payment.refunds.aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
    remaining = q(payment.amount - already)
    if remaining <= 0:
        raise RefundError("Payment is already fully refunded.", code="already_refunded")

    refund_amount = q(amount) if amount is not None else remaining
    if refund_amount <= 0:
        raise RefundError("Refund amount must be positive.", code="invalid_amount")
    if refund_amount > remaining:
        raise RefundError(
            f"Only {remaining} remains refundable.",
            code="amount_exceeds_remaining",
            details={"remaining": str(remaining), "requested": str(refund_amount)},
        )

    provider_ref = _provider_refund(payment, refund_amount)
    refund = Refund.objects.create(
        payment=payment,
        amount=refund_amount,
        reason=reason[:255],
        provider_reference=provider_ref,
        created_by=staff_user,
        idempotency_key=idempotency_key or f"rfnd-{uuid.uuid4()}",
    )

    new_total = already + refund_amount
    if new_total >= payment.amount:
        payment.status = Payment.Status.REFUNDED
        payment.save(update_fields=["status"])
        if order.status != Order.Status.REFUNDED:
            if order.can_transition(Order.Status.REFUNDED):
                transition_order(
                    order,
                    Order.Status.REFUNDED,
                    actor=staff_user,
                    note=f"Full refund {provider_ref}: {reason or 'staff refund'}",
                )
            else:
                # Force terminal state via direct write if machine blocked
                old = order.status
                order.status = Order.Status.REFUNDED
                order.save(update_fields=["status", "updated_at"])
                from apps.orders.models import OrderEvent

                OrderEvent.objects.create(
                    order=order,
                    from_status=old,
                    to_status=Order.Status.REFUNDED,
                    actor=staff_user,
                    note=f"Full refund {provider_ref}",
                )
    else:
        payment.status = Payment.Status.PARTIALLY_REFUNDED
        payment.save(update_fields=["status"])
        from apps.orders.models import OrderEvent

        OrderEvent.objects.create(
            order=order,
            from_status=order.status,
            to_status=order.status,
            actor=staff_user,
            note=f"Partial refund {provider_ref}: {refund_amount} — {reason}",
        )

    # Notify customer
    try:
        from apps.notifications.services import queue_or_send

        queue_or_send(
            to=order.user.email,
            subject=f"Refund for order {order.reference}",
            template="refund_issued",
            context={
                "order": order,
                "refund_amount": f"{refund_amount:.2f}",
                "currency": order.currency,
                "reason": reason,
                "provider_reference": provider_ref,
            },
            user=order.user,
            transactional=True,
        )
    except Exception:
        pass

    return refund
