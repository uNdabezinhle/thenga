"""Catalogue models — Data Model §4."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to="brands/", blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    brand = models.ForeignKey(
        Brand, on_delete=models.PROTECT, related_name="products", null=True, blank=True
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products", null=True, blank=True
    )
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="ZAR")
    is_active = models.BooleanField(default=True)
    # ECTA s42(2) exclusions (e.g. custom goods, sealed audio) — no 7-day cooling-off
    cooling_off_excluded = models.BooleanField(
        default=False,
        help_text="If true, ECTA s44 cooling-off does not apply (s42(2) exclusion).",
    )
    hue = models.PositiveSmallIntegerField(default=150)  # prototype art seed
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["brand", "is_active"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=64, unique=True)
    label = models.CharField(max_length=120)
    price_delta = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("product", "label")
        indexes = [models.Index(fields=["product", "is_active"])]

    def __str__(self):
        return f"{self.product.sku} / {self.label}"

    @property
    def unit_price(self) -> Decimal:
        return self.product.base_price + self.price_delta


class Inventory(models.Model):
    variant = models.OneToOneField(
        ProductVariant, on_delete=models.CASCADE, related_name="inventory"
    )
    quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=3)
    warehouse = models.CharField(max_length=64, default="main")

    def __str__(self):
        return f"Inv<{self.variant_id}: {self.available}>"

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
        """Convert reservation into a sale (decrement both)."""
        self.quantity = max(0, self.quantity - qty)
        self.reserved_quantity = max(0, self.reserved_quantity - qty)
        self.save(update_fields=["quantity", "reserved_quantity"])


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name="images"
    )
    url = models.URLField(blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)


class ProductAttribute(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="attributes")
    key = models.CharField(max_length=64)
    value = models.CharField(max_length=255)

    class Meta:
        ordering = ["id"]


class FlashPrice(models.Model):
    """A dated sale price that replaces the catalogue base while it is live."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="flash_prices")
    sale_price = models.DecimalField(max_digits=12, decimal_places=2)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"Flash<{self.product_id}>"


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    author_display = models.CharField(max_length=120, blank=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("product", "user")
        ordering = ["-created_at"]
