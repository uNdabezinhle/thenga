"""Illustrative Reka packages. Not a charge. Billing comes later."""
from __future__ import annotations

from decimal import Decimal

SAMPLE_SLUG = "northbound"

PACKAGES = (
    {
        "code": "till",
        "name": "Till",
        "monthly_price": Decimal("499.00"),
        "shop": False,
        "pos": True,
        "summary": "Counter sales, receipts, scanner, and drawer. No public shop.",
    },
    {
        "code": "shop",
        "name": "Shop",
        "monthly_price": Decimal("799.00"),
        "shop": True,
        "pos": False,
        "summary": "Public catalogue, cart, and checkout. No till.",
    },
    {
        "code": "shop_till",
        "name": "Shop + Till",
        "monthly_price": Decimal("1099.00"),
        "shop": True,
        "pos": True,
        "summary": "Online shop and counter on the same stock.",
    },
)

ADDONS = (
    {"code": "extra_store", "name": "Another store", "monthly_price": Decimal("199.00"), "summary": "A second location with its own stock."},
    {"code": "live_payfast", "name": "Live PayFast", "monthly_price": Decimal("0.00"), "summary": "Take live card and EFT once your PayFast keys are saved."},
    {"code": "delivery", "name": "Delivery dispatch", "monthly_price": Decimal("149.00"), "summary": "Delivery rates and courier booking."},
    {"code": "loyalty", "name": "Loyalty and referrals", "monthly_price": Decimal("99.00"), "summary": "Points, vouchers, and referral rewards."},
    {"code": "reviews", "name": "Reviews", "monthly_price": Decimal("49.00"), "summary": "Shoppers post product reviews."},
    {"code": "specials", "name": "Flash prices and bundles", "monthly_price": Decimal("99.00"), "summary": "Dated sales and one-key bundles."},
    {"code": "reminders", "name": "Reminders", "monthly_price": Decimal("79.00"), "summary": "Unpaid checkout, low stock, and till-close reminders."},
    {"code": "ads_self_serve", "name": "Reka Ads self-serve", "monthly_price": Decimal("249.00"), "summary": "Write your own shop banners. Not part of ad revenue share."},
    {"code": "turnkey_setup", "name": "Turnkey setup", "monthly_price": Decimal("2500.00"), "summary": "One-time help standing the stack up on your server.", "once_off": True},
)

PACKAGE_BY_CODE = {row["code"]: row for row in PACKAGES}
ADDON_BY_CODE = {row["code"]: row for row in ADDONS}
MERCHANT_AD_SHARE_PERCENT = Decimal("30.00")
# Illustrative rand attributed to one operated click. Not collected from shoppers.
OPERATED_CLICK_GROSS = Decimal("1.00")
TRIAL_DAYS = 14
