"""Public package list and merchant onboarding."""
from __future__ import annotations

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import RekaAPIException
from apps.orders.services import OrderError
from apps.pricing.services import money_str

from .catalog import ADDONS, MERCHANT_AD_SHARE_PERCENT, PACKAGES
from apps.promotions.ads import statement_for

from .models import MerchantMembership
from .services import (
    add_store,
    checklist,
    import_catalogue,
    invite_staff,
    merchant_for,
    open_merchant,
    save_payfast,
)


def _fail(exc: RekaAPIException):
    return Response(
        {"error": {"code": exc.default_code, "message": str(exc.detail)}},
        status=exc.status_code,
    )


def _priced(rows):
    out = []
    for row in rows:
        item = dict(row)
        item["monthly_price"] = money_str(row["monthly_price"])
        item.pop("shop", None)
        item.pop("pos", None)
        out.append(item)
    return out


@api_view(["GET"])
@permission_classes([AllowAny])
def package_list(request):
    return Response(
        {
            "prices_are_illustrative": True,
            "currency": "ZAR",
            "trial_days": 14,
            "packages": [
                {
                    "code": row["code"],
                    "name": row["name"],
                    "monthly_price": money_str(row["monthly_price"]),
                    "shop": row["shop"],
                    "pos": row["pos"],
                    "summary": row["summary"],
                }
                for row in PACKAGES
            ],
            "addons": _priced(ADDONS),
            "included": [
                "Onboarding",
                "Staff login",
                "Tax invoice",
                "Sandbox payments",
                "Transactional email",
            ],
            "ads": {
                "operated_by": "Reka",
                "merchant_share_percent": money_str(MERCHANT_AD_SHARE_PERCENT),
                "self_serve_code": "ads_self_serve",
                "note": "Reka places operated ads and pays the merchant a share. Self-serve banners are a paid extra and are not revenue-share.",
            },
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def onboard(request):
    try:
        merchant = open_merchant(user=request.user, payload=request.data)
    except OrderError as exc:
        return _fail(exc)
    return Response(checklist(merchant, request.user), status=201)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def ad_desk(request):
    merchant = merchant_for(request.user)
    if merchant is None:
        return Response(
            {"error": {"code": "permission_denied", "message": "Open a shop first."}},
            status=403,
        )
    if request.method == "PATCH":
        role = (
            MerchantMembership.objects.filter(merchant=merchant, user=request.user)
            .values_list("role", flat=True)
            .first()
        )
        if role != MerchantMembership.Role.OWNER:
            return Response(
                {"error": {"code": "permission_denied", "message": "Only the owner can change ads."}},
                status=403,
            )
        if "operated_ads" in request.data:
            merchant.operated_ads = bool(request.data.get("operated_ads"))
            merchant.save(update_fields=["operated_ads"])
    today = timezone.now().date().replace(day=1)
    return Response(
        {
            "operated_ads": merchant.operated_ads,
            "statement": statement_for(merchant, today),
        }
    )


def _owner_call(fn, request):
    try:
        return fn(request.user, request.data)
    except OrderError as exc:
        return _fail(exc)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def staff_invite(request):
    result = _owner_call(invite_staff, request)
    if isinstance(result, Response):
        return result
    return Response(result, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def catalogue_import(request):
    result = _owner_call(import_catalogue, request)
    if isinstance(result, Response):
        return result
    return Response({"results": result}, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def store_create(request):
    result = _owner_call(add_store, request)
    if isinstance(result, Response):
        return result
    return Response(
        {
            "code": result.code,
            "name": result.name,
            "sells_online": result.sells_online,
        },
        status=201,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def payfast_keys(request):
    result = _owner_call(save_payfast, request)
    if isinstance(result, Response):
        return result
    return Response(result)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def onboard_status(request):
    merchant = merchant_for(request.user)
    if merchant is None:
        return Response({"merchant": None, "ready": False, "items": []})
    return Response(checklist(merchant, request.user))
