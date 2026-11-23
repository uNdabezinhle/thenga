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
    source = models.CharField(
        max_length=16,
        choices=(("operated", "Operated by Reka"), ("self_serve", "Self-serve")),
        default="operated",
    )
    merchant = models.ForeignKey(
        "platform.Merchant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ads",
    )
    impression_count = models.PositiveIntegerField(default=0)
    click_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title


class AdEvent(models.Model):
    """One placement view or click. Operated clicks feed the monthly share."""

    class Kind(models.TextChoices):
        IMPRESSION = "impression", "Impression"
        CLICK = "click", "Click"

    ad = models.ForeignKey(ShopAd, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["ad", "kind", "created_at"])]


class AdShareStatement(models.Model):
    """Monthly operated-ad share. Illustrative gross, not a shopper charge."""

    merchant = models.ForeignKey(
        "platform.Merchant", on_delete=models.CASCADE, related_name="ad_statements"
    )
    period = models.DateField()
    clicks = models.PositiveIntegerField(default=0)
    gross = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    share_percent = models.DecimalField(max_digits=5, decimal_places=2)
    merchant_share = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reka_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "period"], name="ad_statement_period"),
        ]
        ordering = ["-period"]


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
