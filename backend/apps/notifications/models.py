"""Notification preferences and outbox log — REKA-FR-NOT-* / POPIA s69."""
from __future__ import annotations

from django.conf import settings
from django.db import models


class NotificationPreference(models.Model):
    """Per-user channel/category consent (POPIA s69 marketing)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    email_transactional = models.BooleanField(default=True)  # always on for orders
    email_marketing = models.BooleanField(default=False)  # requires explicit consent
    push_order_updates = models.BooleanField(default=True)
    push_marketing = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Prefs<{self.user_id}>"


class DeviceRegistration(models.Model):
    """FCM/APNs device tokens for push (REKA-FR-NOT-002)."""

    class Platform(models.TextChoices):
        IOS = "ios", "iOS"
        ANDROID = "android", "Android"
        WEB = "web", "Web"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="devices",
    )
    token = models.CharField(max_length=512)
    platform = models.CharField(max_length=16, choices=Platform.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "token")

    def __str__(self):
        return f"Device<{self.platform}:{self.user_id}>"


class NotificationLog(models.Model):
    """Append-only send log for audit and debugging."""

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        PUSH = "push", "Push"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_logs",
    )
    channel = models.CharField(max_length=16, choices=Channel.choices)
    template = models.CharField(max_length=64)
    recipient = models.CharField(max_length=255)
    subject = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    error = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at", "template"])]


class InAppNotification(models.Model):
    class Kind(models.TextChoices):
        ORDER = "order", "Order"
        PROMOTION = "promotion", "Promotion"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inbox",
    )
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.ORDER)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
