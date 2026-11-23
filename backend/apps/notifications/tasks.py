"""Celery tasks for notification dispatch."""
from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    name="notifications.send_email",
)
def send_email_task(self, payload: dict):
    from apps.orders.models import Order

    from .services import send_email

    User = get_user_model()
    user = None
    user_id = payload.pop("user_id", None)
    if user_id:
        user = User.objects.filter(pk=user_id).first()

    from apps.platform.models import Merchant

    merchant = None
    merchant_id = payload.pop("merchant_id", None)
    if merchant_id:
        merchant = Merchant.objects.filter(pk=merchant_id).first()

    context = dict(payload.pop("context", None) or {})
    if "user_id" in context and user:
        context["user"] = user
    order_id = context.pop("order_id", None)
    if order_id:
        order = Order.objects.prefetch_related("items", "shipments").filter(pk=order_id).first()
        if order:
            context["order"] = order
            context["items"] = list(order.items.all())
            shipment = order.shipments.first()
            if shipment and "tracking" not in context:
                context["tracking"] = shipment.tracking_number

    result = send_email(user=user, merchant=merchant, context=context, **payload)
    return {"status": result.status, "log_id": result.id}


@shared_task(name="notifications.send_reminders")
def send_reminders():
    from .reminders import run_reminders

    return run_reminders()
