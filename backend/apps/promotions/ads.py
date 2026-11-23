"""Operated-ad counts and the monthly merchant share. Not a shopper charge."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import F
from django.utils import timezone

from apps.platform.catalog import MERCHANT_AD_SHARE_PERCENT, OPERATED_CLICK_GROSS
from apps.pricing.services import money_str

from .models import AdEvent, AdShareStatement, ShopAd


def _rand(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def record_event(ad: ShopAd, kind: str) -> None:
    if (
        ad.source == "operated"
        and ad.merchant_id
        and not ad.merchant.operated_ads
    ):
        return
    AdEvent.objects.create(ad=ad, kind=kind)
    field = "click_count" if kind == AdEvent.Kind.CLICK else "impression_count"
    ShopAd.objects.filter(pk=ad.pk).update(**{field: F(field) + 1})


def public_ads(placement: str):
    return (
        ShopAd.objects.filter(is_active=True, placement=placement)
        .exclude(source="operated", merchant__operated_ads=False)
        .select_related("merchant")
    )


def _figures(merchant, period: date) -> dict:
    start = timezone.make_aware(datetime(period.year, period.month, 1))
    if period.month == 12:
        end = timezone.make_aware(datetime(period.year + 1, 1, 1))
    else:
        end = timezone.make_aware(datetime(period.year, period.month + 1, 1))
    clicks = AdEvent.objects.filter(
        ad__merchant=merchant,
        ad__source="operated",
        kind=AdEvent.Kind.CLICK,
        created_at__gte=start,
        created_at__lt=end,
    ).count()
    gross = _rand(OPERATED_CLICK_GROSS * clicks)
    share = _rand(gross * MERCHANT_AD_SHARE_PERCENT / Decimal("100"))
    fee = _rand(gross - share)
    return {
        "clicks": clicks,
        "gross": gross,
        "share_percent": MERCHANT_AD_SHARE_PERCENT,
        "merchant_share": share,
        "reka_fee": fee,
    }


def statement_for(merchant, period: date) -> dict:
    figures = _figures(merchant, period)
    return {
        "period": period.isoformat(),
        "clicks": figures["clicks"],
        "gross": money_str(figures["gross"]),
        "share_percent": money_str(figures["share_percent"]),
        "merchant_share": money_str(figures["merchant_share"]),
        "reka_fee": money_str(figures["reka_fee"]),
        "prices_are_illustrative": True,
    }


def close_statement(merchant, period: date) -> AdShareStatement | None:
    figures = _figures(merchant, period)
    if figures["clicks"] == 0:
        return None
    row, _ = AdShareStatement.objects.update_or_create(
        merchant=merchant,
        period=period,
        defaults=figures,
    )
    return row


def previous_month(on: date) -> date:
    return (on.replace(day=1) - timedelta(days=1)).replace(day=1)
