"""Cart models — Data Model §3, ADR-0005."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models


class Cart(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="carts",
    )
    session_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False, session_id__isnull=True)
                    | models.Q(user__isnull=True, session_id__isnull=False)
                ),
                name="cart_single_identity",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user"],
                name="cart_active_user",
                condition=models.Q(is_active=True, user__isnull=False),
            ),
            models.Index(
                fields=["session_id"],
                name="cart_active_session",
                condition=models.Q(is_active=True, session_id__isnull=False),
            ),
        ]

    def __str__(self):
        who = self.user_id or self.session_id
        return f"Cart<{who}>"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "catalogue.Product", on_delete=models.PROTECT, related_name="cart_items"
    )
    variant = models.ForeignKey(
        "catalogue.ProductVariant",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cart_items",
    )
    quantity = models.PositiveSmallIntegerField()
    unit_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("cart", "product", "variant")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="cartitem_qty_positive"
            ),
        ]

    def __str__(self):
        return f"CartItem<{self.product_id} x{self.quantity}>"

    @property
    def line_total(self) -> Decimal:
        return self.unit_price_snapshot * self.quantity


class CartDiscount(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED = "fixed", "Fixed"

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="discounts")
    code = models.CharField(max_length=64)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("cart", "code")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0), name="cartdiscount_amount_nonneg"
            ),
        ]


class ShippingEstimate(models.Model):
    cart = models.ForeignKey(
        Cart, on_delete=models.CASCADE, related_name="shipping_estimates"
    )
    method_name = models.CharField(max_length=64)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    estimated_days = models.CharField(max_length=64)
    is_selected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Coupon(models.Model):
    """Minimal promotions stub for discount codes (Phase 2 bridge)."""

    code = models.CharField(max_length=64, unique=True)
    discount_type = models.CharField(
        max_length=20, choices=CartDiscount.DiscountType.choices
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.code


class SavedForLater(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_items"
    )
    product = models.ForeignKey(
        "catalogue.Product", on_delete=models.CASCADE, related_name="saved_by"
    )
    variant = models.ForeignKey(
        "catalogue.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    unit_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product", "variant")
