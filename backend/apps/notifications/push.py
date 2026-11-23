"""Push notification dispatch — REKA-FR-NOT-002/003.

FCM/APNs integration is stubbed: we log the payload and write NotificationLog
rows so the pipeline is testable. Set FCM_SERVER_KEY later to enable real send.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings

from .models import DeviceRegistration, NotificationLog, NotificationPreference

logger = logging.getLogger(__name__)


def _fcm_enabled() -> bool:
    return bool(getattr(settings, "FCM_SERVER_KEY", "") or "")


def send_push_to_user(
    user,
    *,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    template: str = "push_generic",
) -> list[NotificationLog]:
    """Send (or dry-run) push to all active devices for the user."""
    prefs, _ = NotificationPreference.objects.get_or_create(user=user)
    if not prefs.push_order_updates and template.startswith("order_"):
        return [
            NotificationLog.objects.create(
                user=user,
                channel=NotificationLog.Channel.PUSH,
                template=template,
                recipient=str(user.id),
                subject=title,
                status=NotificationLog.Status.SKIPPED,
                error="push_order_updates disabled",
            )
        ]

    devices = list(
        DeviceRegistration.objects.filter(user=user, is_active=True)
    )
    if not devices:
        return [
            NotificationLog.objects.create(
                user=user,
                channel=NotificationLog.Channel.PUSH,
                template=template,
                recipient=str(user.id),
                subject=title,
                status=NotificationLog.Status.SKIPPED,
                error="no_active_devices",
            )
        ]

    payload = {
        "title": title,
        "body": body,
        "data": data or {},
    }
    logs: list[NotificationLog] = []

    for device in devices:
        log = NotificationLog.objects.create(
            user=user,
            channel=NotificationLog.Channel.PUSH,
            template=template,
            recipient=device.token[:64],
            subject=title,
            status=NotificationLog.Status.QUEUED,
            metadata={
                "platform": device.platform,
                "payload": payload,
            },
        )
        try:
            if _fcm_enabled() and device.platform in (
                DeviceRegistration.Platform.ANDROID,
                DeviceRegistration.Platform.WEB,
            ):
                _send_fcm(device.token, title, body, data or {})
            else:
                # Dry-run: structured log only (no network)
                logger.info(
                    "push.dry_run platform=%s token=%s… title=%s",
                    device.platform,
                    device.token[:12],
                    title,
                )
            log.status = NotificationLog.Status.SENT
            log.save(update_fields=["status"])
        except Exception as exc:
            log.status = NotificationLog.Status.FAILED
            log.error = str(exc)[:1000]
            log.save(update_fields=["status", "error"])
            logger.exception("push.failed device=%s", device.id)
        logs.append(log)
    return logs


def _send_fcm(token: str, title: str, body: str, data: dict) -> None:
    """Minimal FCM HTTP v1-style placeholder using legacy server key if set."""
    import urllib.error
    import urllib.request

    key = settings.FCM_SERVER_KEY
    message = {
        "to": token,
        "notification": {"title": title, "body": body},
        "data": {k: str(v) for k, v in data.items()},
    }
    req = urllib.request.Request(
        "https://fcm.googleapis.com/fcm/send",
        data=json.dumps(message).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"key={key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"FCM HTTP {resp.status}")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"FCM error: {exc.code}") from exc


def notify_order_status_push(order) -> list[NotificationLog]:
    brand = getattr(settings, "REKA_SITE_BRAND_NAME", "Northbound")
    titles = {
        "payment_confirmed": "Payment confirmed",
        "packed": "Order packed",
        "out_for_delivery": "Out for delivery",
        "delivered": "Delivered",
        "cancelled": "Order cancelled",
        "refunded": "Refund processed",
    }
    title = titles.get(order.status, "Order update")
    body = f"{brand} order {order.reference} is now {order.status.replace('_', ' ')}."
    try:
        from apps.notifications.inbox import record_order_notice

        record_order_notice(order)
    except Exception:
        logger.exception("inbox.order_notice failed order=%s", order.reference)
    return send_push_to_user(
        order.user,
        title=title,
        body=body,
        data={
            "order_reference": order.reference,
            "status": order.status,
            "type": "order_status",
        },
        template=f"order_{order.status}",
    )
