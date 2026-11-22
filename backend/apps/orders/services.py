"""Order placement — stock reservation; payment confirmed only via webhook (ADR-0011)."""
from __future__ import annotations

import uuid

from django.db import transaction
from django.utils import timezone

from apps.cart.models import Cart
from apps.cart.services import cart_queryset, cart_totals, ensure_shipping_estimates
from apps.catalogue.models import Inventory
from apps.core.exceptions import CartItemOutOfStock, RekaAPIException

from .models import Address, Order, OrderEvent, OrderItem, Payment, Shipment


class OrderError(RekaAPIException):
    status_code = 400
    default_code = "order_error"


@transaction.atomic
def place_order(
    *,
    user,
    cart: Cart,
    payment_method: str = "card",
    address_text: str = "",
    address: Address | None = None,
    idempotency_key: str | None = None,
    return_url: str = "",
) -> tuple[Order, Payment | None, str]:
    """Create order, reserve stock, start payment.

    Returns (order, payment, redirect_url).
    Payment is confirmed only by webhook (except COD which needs no capture).
    """
    if not user.email_verified and not user.is_superuser:
        raise OrderError(
            "Verify your email before placing an order.",
            code="email_not_verified",
        )

    if idempotency_key:
        existing = Order.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            payment = existing.payments.order_by("-created_at").first()
            redirect = ""
            if payment and payment.status == Payment.Status.PENDING:
                from apps.payments.providers import get_provider

                provider = get_provider(existing.payment_method or "card")
                session = provider.create_checkout(
                    order_reference=existing.reference,
                    amount=existing.grand_total,
                    currency=existing.currency,
                    return_url=return_url,
                    cancel_url=return_url,
                    idempotency_key=idempotency_key,
                )
                # Keep existing provider_reference so webhooks still match
                redirect = session.redirect_url.replace(
                    session.provider_reference, payment.provider_reference
                ) if session.redirect_url else ""
            return existing, payment, redirect

    cart = cart_queryset().get(pk=cart.pk)
    items = list(cart.items.select_related("product", "variant", "variant__inventory"))
    if not items:
        raise OrderError("Cart is empty.", code="cart_empty")

    ensure_shipping_estimates(cart)
    totals = cart_totals(cart)
    selected = cart.shipping_estimates.filter(is_selected=True).first()

    # Reserve stock (not committed until payment webhook)
    for item in items:
        if item.variant_id:
            try:
                inv = Inventory.objects.select_for_update().get(variant_id=item.variant_id)
            except Inventory.DoesNotExist:
                raise CartItemOutOfStock(
                    detail=f"{item.product.name} is out of stock.",
                    details={"product": item.product.name},
                )
            if not inv.reserve(item.quantity):
                raise CartItemOutOfStock(
                    detail=f"Only {inv.available} of {item.product.name} are available.",
                    details={
                        "available": inv.available,
                        "requested": item.quantity,
                        "product": item.product.name,
                    },
                )

    ref = Order.generate_reference()
    while Order.objects.filter(reference=ref).exists():
        ref = Order.generate_reference()

    order = Order.objects.create(
        reference=ref,
        user=user,
        shipping_address=address,
        shipping_address_text=address_text
        or (address.as_single_line() if address else ""),
        status=Order.Status.AWAITING_PAYMENT,
        currency=totals.currency,
        subtotal=totals.subtotal,
        discount_total=totals.discount_total,
        shipping_total=totals.shipping_total,
        tax_total=totals.tax_total,
        grand_total=totals.grand_total,
        shipping_method=selected.method_name if selected else "",
        payment_method=payment_method,
        idempotency_key=idempotency_key or str(uuid.uuid4()),
    )

    for item in items:
        sku = item.variant.sku if item.variant else item.product.sku
        OrderItem.objects.create(
            order=order,
            product=item.product,
            variant=item.variant,
            product_name_snapshot=item.product.name,
            sku_snapshot=sku,
            unit_price=item.unit_price_snapshot,
            quantity=item.quantity,
            line_total=item.unit_price_snapshot * item.quantity,
        )

    OrderEvent.objects.create(
        order=order,
        from_status="",
        to_status=Order.Status.AWAITING_PAYMENT,
        actor=user,
        note="Order placed",
    )

    # Clear cart now — order owns the lines
    cart.items.all().delete()
    cart.discounts.all().delete()

    from apps.payments.services import confirm_payment_from_webhook, initiate_payment

    payment = initiate_payment(
        order, payment_method=payment_method, return_url=return_url
    )
    redirect_url = getattr(payment, "_redirect_url", "") or ""

    # COD: no hosted capture — accept and confirm immediately
    if payment_method == "cod":
        payment = confirm_payment_from_webhook(
            provider_reference=payment.provider_reference,
            status="succeeded",
            amount=payment.amount,
            card_last4="",
            card_brand="",
        )
        order.refresh_from_db()
        redirect_url = ""

    return order, payment, redirect_url


def transition_order(order: Order, new_status: str, actor=None, note: str = "") -> Order:
    if not order.can_transition(new_status):
        raise OrderError(
            f"Cannot transition from {order.status} to {new_status}.",
            code="invalid_transition",
        )
    old = order.status
    order.status = new_status
    order.save(update_fields=["status", "updated_at"])
    OrderEvent.objects.create(
        order=order,
        from_status=old,
        to_status=new_status,
        actor=actor,
        note=note,
    )
    if new_status == Order.Status.OUT_FOR_DELIVERY:
        shipment = order.shipments.first()
        if shipment:
            shipment.status = Shipment.Status.IN_TRANSIT
            shipment.dispatched_at = timezone.now()
            shipment.tracking_number = shipment.tracking_number or f"TRK{order.reference[-6:]}"
            shipment.save()
    if new_status == Order.Status.DELIVERED:
        shipment = order.shipments.first()
        if shipment:
            shipment.status = Shipment.Status.DELIVERED
            shipment.delivered_at = timezone.now()
            shipment.save()

    # Push on status change (REKA-FR-NOT-003) — never block the transition
    try:
        from apps.notifications.push import notify_order_status_push

        notify_order_status_push(order)
    except Exception:
        pass
    return order


def advance_order(order: Order, actor=None) -> Order:
    """Simulate next webhook / fulfilment step for demo tracking."""
    stages = Order.TRACKING_STAGES
    try:
        idx = stages.index(order.status)
    except ValueError:
        return order
    if idx >= len(stages) - 1:
        return order
    # Cannot advance past awaiting_payment without a real payment confirm
    if order.status == Order.Status.AWAITING_PAYMENT:
        raise OrderError(
            "Pay for this order before fulfilment can start.",
            code="payment_required",
        )
    nxt = stages[idx + 1]
    order = transition_order(order, nxt, actor=actor, note="Status advanced")
    if nxt == Order.Status.OUT_FOR_DELIVERY:
        try:
            from apps.notifications.services import notify_order_dispatched

            notify_order_dispatched(order)
        except Exception:
            pass
    return order


@transaction.atomic
def cancel_order(order: Order, actor=None, note: str = "Cancelled") -> Order:
    """Cancel before dispatch; release reservation or restock committed units."""
    if order.status in (
        Order.Status.OUT_FOR_DELIVERY,
        Order.Status.DELIVERED,
        Order.Status.CANCELLED,
        Order.Status.REFUNDED,
    ):
        raise OrderError(
            "This order can no longer be cancelled.",
            code="invalid_transition",
        )
    for item in order.items.select_related("variant").all():
        if not item.variant_id:
            continue
        try:
            inv = Inventory.objects.select_for_update().get(variant_id=item.variant_id)
        except Inventory.DoesNotExist:
            continue
        if order.status == Order.Status.AWAITING_PAYMENT:
            inv.release(item.quantity)
        else:
            inv.quantity += item.quantity
            inv.save(update_fields=["quantity"])
    return transition_order(
        order, Order.Status.CANCELLED, actor=actor, note=note
    )
