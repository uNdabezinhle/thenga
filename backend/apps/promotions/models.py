"""Personal vouchers and first-party shop banners."""
from __future__ import annotations

from django.conf import settings
from django.db import models


class Voucher(models.Model):
    code = models.CharField(max_length=64, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vouchers",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2)
    expires_at = models.DateTimeField(null=True, blank=True)
    redeemed_order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="redeemed_vouchers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class ShopAd(models.Model):
    class Placement(models.TextChoices):
        SHOP_TOP = "shop_top", "Shop top"

    title = models.CharField(max_length=120)
    body = models.CharField(max_length=255, blank=True)
    placement = models.CharField(
        max_length=32, choices=Placement.choices, default=Placement.SHOP_TOP
    )
    product_slug = models.CharField(max_length=160, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title
