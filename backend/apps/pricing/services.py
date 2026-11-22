"""Single pricing service — ADR-0009.

All money is Decimal, quantised ROUND_HALF_UP at each step, floored at zero.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

TWO = Decimal("0.01")
ZERO = Decimal("0.00")


def q(amount: Decimal | int | float | str) -> Decimal:
    return Decimal(str(amount)).quantize(TWO, rounding=ROUND_HALF_UP)


def money_str(amount: Decimal) -> str:
    return f"{q(amount):.2f}"


@dataclass
class Line:
    unit_price: Decimal
    quantity: int


@dataclass
class Totals:
    subtotal: Decimal
    discount_total: Decimal
    shipping_total: Decimal
    tax_total: Decimal
    grand_total: Decimal
    currency: str = "ZAR"

    def as_dict(self) -> dict:
        return {
            "subtotal": money_str(self.subtotal),
            "discount_total": money_str(self.discount_total),
            "shipping_total": money_str(self.shipping_total),
            "tax_total": money_str(self.tax_total),
            "grand_total": money_str(self.grand_total),
            "currency": self.currency,
        }


def line_total(unit_price: Decimal, quantity: int) -> Decimal:
    return q(q(unit_price) * quantity)


def cart_subtotal(lines: Iterable[Line]) -> Decimal:
    total = ZERO
    for line in lines:
        total = q(total + line_total(line.unit_price, line.quantity))
    return total


def apply_discounts(
    subtotal: Decimal,
    discounts: Iterable[tuple[str, Decimal]],
) -> Decimal:
    """discounts: iterable of (type, amount) where type is 'percentage' or 'fixed'.

    Caps total discount at subtotal so grand total never goes negative.
    """
    remaining = q(subtotal)
    applied = ZERO
    for dtype, amount in discounts:
        amount = q(amount)
        if dtype == "percentage":
            # clamp percentage to 0–100
            pct = min(max(amount, ZERO), Decimal("100"))
            d = q(remaining * pct / Decimal("100"))
        else:
            d = amount
        d = min(d, remaining)
        applied = q(applied + d)
        remaining = q(remaining - d)
        if remaining <= ZERO:
            break
    return applied


def compute_totals(
    *,
    lines: Iterable[Line],
    discounts: Iterable[tuple[str, Decimal]] | None = None,
    shipping: Decimal | int | float | str = ZERO,
    tax: Decimal | int | float | str = ZERO,
    currency: str = "ZAR",
) -> Totals:
    subtotal = cart_subtotal(lines)
    discount_total = apply_discounts(subtotal, discounts or [])
    shipping_total = q(shipping)
    tax_total = q(tax)
    grand = q(subtotal - discount_total + shipping_total + tax_total)
    if grand < ZERO:
        grand = ZERO
    return Totals(
        subtotal=subtotal,
        discount_total=discount_total,
        shipping_total=shipping_total,
        tax_total=tax_total,
        grand_total=grand,
        currency=currency,
    )
