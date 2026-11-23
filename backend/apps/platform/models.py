"""A merchant is one business on Reka. Northbound is the sample."""
from __future__ import annotations

from django.conf import settings
from django.db import models


class Merchant(models.Model):
    class Status(models.TextChoices):
        TRIALING = "trialing", "Trialing"
        ACTIVE = "active", "Active"
        READ_ONLY = "read_only", "Read only"

    slug = models.SlugField(unique=True)
    trading_name = models.CharField(max_length=120)
    legal_name = models.CharField(max_length=160, blank=True)
    vat_number = models.CharField(max_length=32, blank=True)
    city = models.CharField(max_length=120, blank=True)
    support_email = models.EmailField(blank=True)
    package = models.CharField(max_length=32)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TRIALING)
    trial_ends = models.DateTimeField(null=True, blank=True)
    empty_catalogue_ok = models.BooleanField(default=False)
    privacy_accepted = models.BooleanField(default=False)
    operated_ads = models.BooleanField(
        default=True,
        help_text="Reka may place operated ads. The merchant cannot edit those creatives.",
    )
    payfast_merchant_id = models.CharField(max_length=64, blank=True)
    payfast_merchant_key = models.CharField(max_length=64, blank=True)
    payfast_passphrase = models.CharField(max_length=128, blank=True)
    payfast_sandbox = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["trading_name"]

    def __str__(self):
        return self.trading_name


class MerchantMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        STAFF = "staff", "Staff"

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="merchant_memberships"
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.STAFF)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "user"], name="platform_member_once"),
        ]


class MerchantAddOn(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="addons")
    code = models.CharField(max_length=32)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "code"], name="platform_addon_once"),
        ]
