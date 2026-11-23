"""Orders & payments — Data Model §5."""
from __future__ import annotations

import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models


class Address(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses"
    )
    label = models.CharField(max_length=64, blank=True, default="Home")
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    suburb = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120)
    province = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=2, default="ZA")
    recipient_name = models.CharField(max_length=200)
    recipient_phone = models.CharField(max_length=32, blank=True)
    is_default_shipping = models.BooleanField(default=False)
    is_default_billing = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.recipient_name}, {self.city}"

    def as_single_line(self) -> str:
        parts = [self.line1, self.line2, self.suburb, self.city, self.postal_code]
        return ", ".join(p for p in parts if p)


class Order(models.Model):
    class Channel(models.TextChoices):
        ONLINE = "online", "Online"
        POS = "pos", "Point of sale"

    class Status(models.TextChoices):
        AWAITING_PAYMENT = "awaiting_payment", "Awaiting payment"
        PAYMENT_CONFIRMED = "payment_confirmed", "Payment confirmed"
        PACKED = "packed", "Packed"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for delivery"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    # Explicit state machine transitions
    ALLOWED_TRANSITIONS = {
        Status.AWAITING_PAYMENT: {Status.PAYMENT_CONFIRMED, Status.CANCELLED},
        Status.PAYMENT_CONFIRMED: {Status.PACKED, Status.CANCELLED, Status.REFUNDED},
        Status.PACKED: {Status.OUT_FOR_DELIVERY, Status.CANCELLED, Status.REFUNDED},
        Status.OUT_FOR_DELIVERY: {Status.DELIVERED, Status.REFUNDED},
        Status.DELIVERED: {Status.REFUNDED},
        Status.CANCELLED: set(),
        Status.REFUNDED: set(),
    }

    TRACKING_STAGES = [
        Status.AWAITING_PAYMENT,
        Status.PAYMENT_CONFIRMED,
        Status.PACKED,
        Status.OUT_FOR_DELIVERY,
        Status.DELIVERED,
    ]

    reference = models.CharField(max_length=32, unique=True, db_index=True)
    channel = models.CharField(
        max_length=16, choices=Channel.choices, default=Channel.ONLINE, db_index=True
    )
    store = models.ForeignKey(
        "pos.Store",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders",
    )
    merchant = models.ForeignKey(
        "platform.Merchant",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )
    shipping_address = models.ForeignKey(
        Address, on_delete=models.PROTECT, related_name="orders", null=True, blank=True
    )
    shipping_address_text = models.TextField(blank=True)
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.AWAITING_PAYMENT
    )
    currency = models.CharField(max_length=3, default="ZAR")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    shipping_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    grand_total = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_method = models.CharField(max_length=64, blank=True)
    payment_method = models.CharField(max_length=32, blank=True)
    discount_code = models.CharField(max_length=64, blank=True)
    discount_settled = models.BooleanField(default=False)
    loyalty_points = models.PositiveIntegerField(default=0)
    specials_awarded = models.BooleanField(default=False)
    idempotency_key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    placed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-placed_at"]
        indexes = [
            models.Index(fields=["user", "-placed_at"]),
        ]

    def __str__(self):
        return self.reference

    @staticmethod
    def generate_reference() -> str:
        return f"NB-{secrets.randbelow(900000) + 100000}"

    def can_transition(self, new_status: str) -> bool:
        allowed = self.ALLOWED_TRANSITIONS.get(self.status, set())
        return new_status in allowed

    @property
    def tracking_stage(self) -> int:
        try:
            return self.TRACKING_STAGES.index(self.status)
        except ValueError:
            return 0


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "catalogue.Product", on_delete=models.PROTECT, related_name="order_items"
    )
    variant = models.ForeignKey(
        "catalogue.ProductVariant",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="order_items",
    )
    product_name_snapshot = models.CharField(max_length=255)
    sku_snapshot = models.CharField(max_length=64)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveSmallIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)


class OrderEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=32, blank=True)
    to_status = models.CharField(max_length=32)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        PARTIALLY_REFUNDED = "partially_refunded", "Partially refunded"
        REFUNDED = "refunded", "Refunded"

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=32, default="sandbox")
    provider_reference = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="ZAR")
    card_last4 = models.CharField(max_length=4, blank=True)
    card_brand = models.CharField(max_length=32, blank=True)
    idempotency_key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def refunded_total(self):
        from django.db.models import Sum

        total = self.refunds.aggregate(s=Sum("amount"))["s"]
        return total or Decimal("0.00")

    @property
    def refundable_remaining(self):
        return self.amount - self.refunded_total


class Refund(models.Model):
    """Staff-initiated full/partial refund via provider (REKA-FR-PAY-006)."""

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True)
    provider_reference = models.CharField(max_length=128, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refunds_issued",
    )
    idempotency_key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Refund<{self.provider_reference or self.pk}>"


class Shipment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DISPATCHED = "dispatched", "Dispatched"
        IN_TRANSIT = "in_transit", "In transit"
        DELIVERED = "delivered", "Delivered"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="shipments")
    carrier = models.CharField(max_length=64, blank=True, default="")
    tracking_number = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]


class ShipmentEvent(models.Model):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=20)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class ShippingRate(models.Model):
    """Domestic delivery price the sandbox courier quotes."""

    method_name = models.CharField(max_length=64, unique=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    estimated_days = models.CharField(max_length=64)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.method_name
