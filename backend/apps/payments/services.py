"""Payment confirmation — webhook is the only source of truth (REKA-FR-PAY-003)."""
from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import RekaAPIException
from apps.orders.models import Order, OrderEvent, Payment, Shipment
from apps.orders.services import OrderError, transition_order

from .providers import SandboxProvider, get_provider

logger = logging.getLogger(__name__)


class PaymentError(RekaAPIException):
    status_code = 400
    default_code = "payment_error"


@transaction.atomic
def initiate_payment(order: Order, *, payment_method: str, return_url: str = "") -> Payment:
    """Create a pending Payment and provider checkout session."""
    if order.status != Order.Status.AWAITING_PAYMENT:
        raise PaymentError("Order is not awaiting payment.", code="order_not_payable")

    existing = order.payments.filter(status=Payment.Status.PENDING).first()
    if existing:
        return existing

    from apps.payments.providers import payfast_for_order

    if payment_method in ("card", "eft", "payfast") and getattr(order, "merchant_id", None):
        merchant_provider = payfast_for_order(order)
        if merchant_provider.merchant_id and order.merchant.payfast_merchant_id:
            provider = merchant_provider
        else:
            provider = get_provider(payment_method)
    else:
        provider = get_provider(payment_method)
    session = provider.create_checkout(
        order_reference=order.reference,
        amount=order.grand_total,
        currency=order.currency,
        return_url=return_url or "",
        cancel_url=return_url or "",
        idempotency_key=order.idempotency_key or str(uuid.uuid4()),
    )

    payment = Payment.objects.create(
        order=order,
        provider=session.provider,
        provider_reference=session.provider_reference,
        status=Payment.Status.PENDING,
        amount=order.grand_total,
        currency=order.currency,
        card_last4="",
        card_brand="",
        idempotency_key=f"pay-{order.idempotency_key or order.reference}",
    )
    # Stash redirect / form on a non-model attribute for the API response
    payment._redirect_url = session.redirect_url
    payment._form_fields = session.form_fields
    payment._form_action = session.form_action
    return payment


@transaction.atomic
def confirm_payment_from_webhook(
    *,
    provider_reference: str,
    status: str,
    amount: Decimal | None = None,
    card_last4: str = "",
    card_brand: str = "",
    event_id: str | None = None,
) -> Payment:
    """Idempotent payment confirmation. Only path that marks orders paid."""
    try:
        payment = (
            Payment.objects.select_for_update()
            .select_related("order", "order__store")
            .get(provider_reference=provider_reference)
        )
    except Payment.DoesNotExist:
        raise PaymentError("Unknown payment reference.", code="payment_not_found")

    # Idempotency: already processed
    if payment.status == Payment.Status.SUCCEEDED:
        return payment

    if status not in ("succeeded", "paid", "complete", "success"):
        return mark_payment_failed(payment)

    if amount is not None and Decimal(str(amount)) != payment.amount:
        raise PaymentError(
            "Webhook amount does not match payment.",
            code="payment_amount_mismatch",
        )

    order = payment.order
    if order.status == Order.Status.PAYMENT_CONFIRMED:
        payment.status = Payment.Status.SUCCEEDED
        payment.card_last4 = card_last4 or payment.card_last4
        payment.card_brand = card_brand or payment.card_brand
        payment.save(update_fields=["status", "card_last4", "card_brand"])
        return payment

    payment.status = Payment.Status.SUCCEEDED
    payment.card_last4 = card_last4
    payment.card_brand = card_brand
    payment.save(update_fields=["status", "card_last4", "card_brand"])

    if order.status == Order.Status.AWAITING_PAYMENT:
        transition_order(
            order,
            Order.Status.PAYMENT_CONFIRMED,
            actor=None,
            note=f"Payment confirmed via webhook ({payment.provider})",
        )
        # Commit reserved stock. A till at a separate store does not touch the website warehouse.
        from apps.pos.stock import locked_stock

        for item in order.items.select_related("variant").all():
            if not item.variant_id:
                continue
            locked_stock(order, item.variant_id).commit(item.quantity)

        if order.channel != Order.Channel.POS and not order.shipments.exists():
            Shipment.objects.create(order=order, status=Shipment.Status.PENDING)
        from apps.promotions.services import settle_order_discount
        from apps.promotions.specials import award_order_specials

        settle_order_discount(order)
        award_order_specials(order)

    logger.info(
        "payment.confirmed ref=%s order=%s event=%s",
        provider_reference,
        order.reference,
        event_id,
    )

    # Fire-and-forget order confirmation email (REKA-FR-NOT-001)
    try:
        from apps.notifications.services import notify_order_confirmation

        notify_order_confirmation(order)
    except Exception:
        logger.exception("order confirmation email failed for %s", order.reference)

    return payment


def mark_payment_failed(payment: Payment) -> Payment:
    """Record one failed attempt and send the transactional mail once."""
    if payment.status in (Payment.Status.FAILED, Payment.Status.SUCCEEDED):
        return payment
    payment.status = Payment.Status.FAILED
    payment.save(update_fields=["status"])
    try:
        order = Order.objects.select_related("user", "merchant").get(pk=payment.order_id)
        from apps.notifications.services import notify_payment_failed

        notify_payment_failed(order)
    except Exception:
        logger.exception("payment failed email failed for payment %s", payment.pk)
    return payment


def process_sandbox_webhook(raw_body: bytes, signature: str | None) -> Payment:
    provider = SandboxProvider()
    if not provider.verify_webhook(raw_body, signature):
        raise PaymentError("Invalid webhook signature.", code="webhook_signature_invalid")
    try:
        data = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PaymentError("Malformed webhook body.", code="webhook_invalid") from exc

    return confirm_payment_from_webhook(
        provider_reference=data["provider_reference"],
        status=data.get("status", "succeeded"),
        amount=Decimal(str(data["amount"])) if "amount" in data else None,
        card_last4=data.get("card_last4", "4242"),
        card_brand=data.get("card_brand", "Visa"),
        event_id=data.get("event_id"),
    )


def simulate_sandbox_success(payment: Payment) -> Payment:
    """Dev helper: build a signed webhook and process it."""
    provider = SandboxProvider()
    body = json.dumps(
        {
            "provider_reference": payment.provider_reference,
            "status": "succeeded",
            "amount": str(payment.amount),
            "card_last4": "4242",
            "card_brand": "Visa",
            "event_id": str(uuid.uuid4()),
        }
    ).encode("utf-8")
    sig = provider.sign(body)
    return process_sandbox_webhook(body, sig)
