"""Synchronous email helpers + preference checks."""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from .models import NotificationLog, NotificationPreference

logger = logging.getLogger(__name__)

BRAND = getattr(settings, "REKA_SITE_BRAND_NAME", "Northbound")
PLATFORM_NAME = "Reka"


def get_or_create_prefs(user) -> NotificationPreference:
    prefs, _ = NotificationPreference.objects.get_or_create(user=user)
    return prefs


def send_email(
    *,
    to: str,
    subject: str,
    template: str,
    context: dict[str, Any] | None = None,
    user=None,
    merchant=None,
    metadata: dict | None = None,
    transactional: bool = True,
) -> NotificationLog:
    """Render template and send. Marketing emails require consent."""
    brand = merchant.trading_name if merchant is not None else BRAND
    footer = f"Sent with {PLATFORM_NAME}" if merchant is not None else ""
    ctx = {
        "brand": brand,
        "platform_footer": footer,
        "public_base": settings.PUBLIC_API_BASE,
        **(context or {}),
    }
    extra = {"transactional": transactional, **(metadata or {})}

    if user and not transactional:
        prefs = get_or_create_prefs(user)
        if not prefs.email_marketing:
            log = NotificationLog.objects.create(
                user=user,
                merchant=merchant,
                channel=NotificationLog.Channel.EMAIL,
                template=template,
                recipient=to,
                subject=subject,
                status=NotificationLog.Status.SKIPPED,
                error="No marketing consent (POPIA s69)",
                metadata=extra,
            )
            return log

    log = NotificationLog.objects.create(
        user=user,
        merchant=merchant,
        channel=NotificationLog.Channel.EMAIL,
        template=template,
        recipient=to,
        subject=subject,
        status=NotificationLog.Status.QUEUED,
        metadata=extra,
    )

    try:
        text_body = render_to_string(f"notifications/{template}.txt", ctx)
        html_body = render_to_string(f"notifications/{template}.html", ctx)
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        log.status = NotificationLog.Status.SENT
        log.save(update_fields=["status"])
        logger.info("email.sent template=%s to=%s", template, to)
    except Exception as exc:
        log.status = NotificationLog.Status.FAILED
        log.error = str(exc)[:1000]
        log.save(update_fields=["status", "error"])
        logger.exception("email.failed template=%s to=%s", template, to)
    return log


def queue_or_send(**kwargs) -> NotificationLog:
    """Prefer Celery when broker is configured and not eager; else send inline."""
    use_celery = bool(getattr(settings, "CELERY_BROKER_URL", None)) and not getattr(
        settings, "CELERY_TASK_ALWAYS_EAGER", True
    )
    if not use_celery:
        return send_email(**kwargs)
    try:
        from .tasks import send_email_task

        user = kwargs.get("user")
        merchant = kwargs.get("merchant")
        payload = {
            "to": kwargs["to"],
            "subject": kwargs["subject"],
            "template": kwargs["template"],
            "context": _json_safe_context(kwargs.get("context")),
            "transactional": kwargs.get("transactional", True),
            "metadata": kwargs.get("metadata") or {},
            "user_id": user.id if user is not None else None,
            "merchant_id": merchant.id if merchant is not None else None,
        }
        send_email_task.delay(payload)
        return NotificationLog.objects.create(
            user=user,
            merchant=merchant,
            channel=NotificationLog.Channel.EMAIL,
            template=kwargs.get("template", ""),
            recipient=kwargs.get("to", ""),
            subject=kwargs.get("subject", ""),
            status=NotificationLog.Status.QUEUED,
            metadata={"async": True},
        )
    except Exception:
        logger.warning("celery unavailable; sending email inline")
        return send_email(**kwargs)


def _json_safe_context(context: dict | None) -> dict:
    """Strip non-serialisable model objects for the broker; re-hydrate in task."""
    if not context:
        return {}
    safe = {}
    for key, value in context.items():
        if key == "user" and hasattr(value, "id"):
            safe["user_id"] = value.id
        elif key == "order" and hasattr(value, "id"):
            safe["order_id"] = value.id
        elif key == "items":
            continue  # reloaded from order
        elif isinstance(value, (str, int, float, bool, type(None))):
            safe[key] = value
        else:
            safe[key] = str(value)
    return safe


# --- domain helpers ---------------------------------------------------------

def notify_email_verification(user, token: str) -> NotificationLog:
    link = f"{settings.PUBLIC_API_BASE}/api/v1/auth/email/verify/?token={token}"
    return queue_or_send(
        to=user.email,
        subject=f"Verify your {BRAND} email",
        template="email_verification",
        context={"user": user, "token": token, "link": link},
        user=user,
        transactional=True,
    )


def notify_password_reset(user, token: str) -> NotificationLog:
    link = f"{settings.PUBLIC_API_BASE}/#reset?token={token}"
    return queue_or_send(
        to=user.email,
        subject=f"Reset your {BRAND} password",
        template="password_reset",
        context={"user": user, "token": token, "link": link},
        user=user,
        transactional=True,
    )


def _order_merchant(order):
    from apps.platform.models import Merchant

    ids = {
        item.product.merchant_id
        for item in order.items.select_related("product")
        if item.product.merchant_id
    }
    if len(ids) != 1:
        return None
    return Merchant.objects.filter(pk=next(iter(ids))).first()


def notify_payment_failed(order) -> NotificationLog:
    merchant = order.merchant if getattr(order, "merchant_id", None) else _order_merchant(order)
    brand = merchant.trading_name if merchant is not None else BRAND
    return queue_or_send(
        to=order.user.email,
        subject=f"{brand} payment for {order.reference} did not go through",
        template="payment_failed",
        context={
            "reference": order.reference,
            "amount": f"{order.grand_total:.2f}",
            "currency": order.currency,
        },
        user=order.user,
        merchant=merchant,
        metadata={"order_id": order.id},
        transactional=True,
    )


def notify_order_confirmation(order) -> NotificationLog:
    merchant = _order_merchant(order)
    brand = merchant.trading_name if merchant is not None else BRAND
    return queue_or_send(
        to=order.user.email,
        subject=f"{brand} order {order.reference} confirmed",
        template="order_confirmation",
        context={
            "order": order,
            "items": list(order.items.all()),
            "grand_total": f"{order.grand_total:.2f}",
            "currency": order.currency,
        },
        user=order.user,
        merchant=merchant,
        transactional=True,
    )


def notify_order_dispatched(order) -> NotificationLog:
    shipment = order.shipments.first()
    return queue_or_send(
        to=order.user.email,
        subject=f"{BRAND} order {order.reference} is on its way",
        template="order_dispatched",
        context={
            "order": order,
            "tracking": shipment.tracking_number if shipment else "",
        },
        user=order.user,
        transactional=True,
    )
