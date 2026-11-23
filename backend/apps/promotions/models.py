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


class Bundle(models.Model):
    title = models.CharField(max_length=120, unique=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class BundleItem(models.Model):
    bundle = models.ForeignKey(Bundle, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "catalogue.Product", on_delete=models.PROTECT, related_name="bundle_items"
    )
    variant = models.ForeignKey(
        "catalogue.ProductVariant",
        on_delete=models.PROTECT,
        related_name="bundle_items",
    )
    quantity = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["id"]


class LoyaltyAccount(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loyalty",
    )
    points = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Loyalty<{self.user_id}:{self.points}>"


class ReferralProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referral",
    )
    code = models.CharField(max_length=16, unique=True)
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referred_customers",
    )
    settled = models.BooleanField(default=False)
    rewarded_order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referral_rewards",
    )
    reward_voucher = models.ForeignKey(
        Voucher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referral_rewards",
    )
    referrer_points = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.code
