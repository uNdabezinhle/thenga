"""Courier providers. The sandbox books a tracking number on this API and does not call out."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class CourierQuote:
    method_name: str
    price: Decimal
    estimated_days: str


@dataclass(frozen=True)
class CourierBooking:
    carrier: str
    tracking_number: str


DEFAULT_QUOTES = (
    ("Standard", Decimal("0.00"), "5 – 7 days"),
    ("Express", Decimal("14.50"), "2 days"),
    ("Next day", Decimal("29.00"), "Tomorrow before 12:00"),
)


def ensure_shipping_rates():
    """Create the three domestic rates the first time a quote is asked for."""
    from apps.orders.models import ShippingRate

    existing = list(ShippingRate.objects.all())
    if existing:
        return existing
    return [
        ShippingRate.objects.create(
            method_name=name,
            price=price,
            estimated_days=days,
            sort_order=index,
        )
        for index, (name, price, days) in enumerate(DEFAULT_QUOTES)
    ]


class CourierProvider(Protocol):
    name: str

    def quote(self) -> list[CourierQuote]: ...

    def book(self, *, order_reference: str) -> CourierBooking: ...


class SandboxCourier:
    """Domestic demo rates and a local waybill. No carrier HTTP call."""

    name = "sandbox"

    def quote(self) -> list[CourierQuote]:
        return [
            CourierQuote(row.method_name, row.price, row.estimated_days)
            for row in ensure_shipping_rates()
        ]

    def book(self, *, order_reference: str) -> CourierBooking:
        del order_reference
        number = f"SBX{uuid.uuid4().hex[:8].upper()}"
        return CourierBooking(carrier="Northbound Courier", tracking_number=number)


def get_courier() -> CourierProvider:
    name = (getattr(settings, "COURIER_PROVIDER", None) or "sandbox").lower()
    if name == "sandbox":
        return SandboxCourier()
    raise ImproperlyConfigured(
        f"Unknown COURIER_PROVIDER '{name}'. Supported value: sandbox."
    )
