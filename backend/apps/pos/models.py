"""Till stores, their own stock, and the cash drawer.

Harbour sells from the website warehouse. Any other store keeps StoreStock
so a trail-shop sale cannot take a unit the website still has.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models


class Store(models.Model):
    merchant = models.ForeignKey(
        "platform.Merchant",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stores",
    )
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    sells_online = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StoreStock(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="stock")
    variant = models.ForeignKey(
        "catalogue.ProductVariant", on_delete=models.CASCADE, related_name="store_stock"
    )
    quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["store", "variant"], name="pos_store_variant"),
        ]

    def __str__(self):
        return f"{self.store_id}:{self.variant_id}"

    @property
    def available(self) -> int:
        return max(0, self.quantity - self.reserved_quantity)

    def reserve(self, qty: int) -> bool:
        if self.available < qty:
            return False
        self.reserved_quantity += qty
        self.save(update_fields=["reserved_quantity"])
        return True

    def release(self, qty: int) -> None:
        self.reserved_quantity = max(0, self.reserved_quantity - qty)
        self.save(update_fields=["reserved_quantity"])

    def commit(self, qty: int) -> None:
        self.quantity = max(0, self.quantity - qty)
        self.reserved_quantity = max(0, self.reserved_quantity - qty)
        self.save(update_fields=["quantity", "reserved_quantity"])


class StoreCatalogItem(models.Model):
    """Optional per-store list. No rows means the shared till catalogue."""

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="catalog_items")
    variant = models.ForeignKey(
        "catalogue.ProductVariant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="store_catalog_items",
    )
    bundle = models.ForeignKey(
        "promotions.Bundle",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="store_catalog_items",
    )
    price_override = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["store", "variant"],
                condition=models.Q(variant__isnull=False),
                name="pos_catalog_variant",
            ),
            models.UniqueConstraint(
                fields=["store", "bundle"],
                condition=models.Q(bundle__isnull=False),
                name="pos_catalog_bundle",
            ),
        ]


class DrawerSession(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="drawers")
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="drawers_opened"
    )
    opening_float = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    closing_count = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expected = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]


class DrawerMovement(models.Model):
    class Kind(models.TextChoices):
        SALE = "sale", "Sale"
        PAY_IN = "pay_in", "Pay in"
        PAY_OUT = "pay_out", "Pay out"

    session = models.ForeignKey(
        DrawerSession, on_delete=models.CASCADE, related_name="movements"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drawer_movements",
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
