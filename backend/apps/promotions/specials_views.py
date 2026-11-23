"""Customer and staff endpoints for flash prices, bundles, points, and referrals."""
from __future__ import annotations

from decimal import Decimal

from django.shortcuts import get_object_or_404
from datetime import datetime

from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffRole
from apps.cart.serializers import CartSerializer
from apps.cart.services import cart_queryset, get_or_create_cart
from apps.catalogue.models import FlashPrice
from apps.pricing.services import money_str
from apps.promotions.models import Bundle
from apps.promotions.specials import (
    add_bundle_to_cart,
    attach_referrer,
    ensure_referral,
    loyalty_account,
    redeem_points,
)


def _flash_payload(row: FlashPrice) -> dict:
    return {
        "id": row.id,
        "product_id": row.product_id,
        "product_name": row.product.name,
        "sale_price": money_str(row.sale_price),
        "compare_at": money_str(row.product.base_price),
        "starts_at": row.starts_at,
        "ends_at": row.ends_at,
        "is_active": row.is_active,
    }


def _bundle_payload(bundle: Bundle) -> dict:
    items = []
    compare = Decimal("0.00")
    for row in bundle.items.select_related("product", "variant"):
        items.append(
            {
                "product_id": row.product_id,
                "name": row.product.name,
                "quantity": row.quantity,
            }
        )
        compare += row.variant.unit_price * row.quantity
    return {
        "id": bundle.id,
        "title": bundle.title,
        "price": money_str(bundle.price),
        "compare_at": money_str(compare),
        "is_active": bundle.is_active,
        "items": items,
    }


class BundleListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        rows = Bundle.objects.filter(is_active=True).prefetch_related("items__product", "items__variant")
        return Response({"results": [_bundle_payload(row) for row in rows]})


class BundleAddView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk):
        bundle = get_object_or_404(Bundle, pk=pk)
        cart = get_or_create_cart(request)
        add_bundle_to_cart(cart, bundle)
        fresh = cart_queryset().get(pk=cart.pk)
        return Response(CartSerializer(fresh).data)


class LoyaltyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = ensure_referral(request.user)
        referrer_code = ""
        if profile.referrer_id:
            referrer = ensure_referral(profile.referrer)
            referrer_code = referrer.code
        return Response(
            {
                "points": loyalty_account(request.user).points,
                "referral_code": profile.code,
                "referrer_code": referrer_code,
            }
        )


class LoyaltyRedeemView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        voucher = redeem_points(request.user)
        return Response(
            {
                "points": loyalty_account(request.user).points,
                "voucher_code": voucher.code,
                "amount": money_str(voucher.amount),
            }
        )


class ReferralView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = attach_referrer(request.user, str(request.data.get("code") or ""))
        return Response({"referrer_code": ensure_referral(profile.referrer).code})


class StaffFlashListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request):
        rows = FlashPrice.objects.select_related("product").all()
        return Response({"results": [_flash_payload(row) for row in rows]})


class StaffFlashDetailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffRole]

    def patch(self, request, pk):
        from apps.platform.services import merchant_for, require_addon

        row = get_object_or_404(FlashPrice.objects.select_related("product"), pk=pk)
        require_addon(merchant_for(request.user), "specials")
        require_addon(row.product.merchant, "specials")
        data = request.data
        if "sale_price" in data:
            try:
                amount = Decimal(str(data.get("sale_price")))
            except Exception:
                return Response({"sale_price": "Enter a price."}, status=400)
            if amount < 0:
                return Response({"sale_price": "Price cannot be negative."}, status=400)
            row.sale_price = amount
        if "is_active" in data:
            row.is_active = bool(data.get("is_active"))
        for field in ("starts_at", "ends_at"):
            if field not in data:
                continue
            raw = data.get(field)
            if raw in (None, ""):
                setattr(row, field, None)
                continue
            try:
                parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                return Response({field: "Use an ISO date and time."}, status=400)
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            setattr(row, field, parsed)
        row.save()
        return Response(_flash_payload(row))


class StaffBundleListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request):
        rows = Bundle.objects.prefetch_related("items__product", "items__variant")
        return Response({"results": [_bundle_payload(row) for row in rows]})


class StaffBundleDetailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffRole]

    def patch(self, request, pk):
        bundle = get_object_or_404(Bundle, pk=pk)
        data = request.data
        if "title" in data:
            title = str(data.get("title") or "").strip()
            if not title:
                return Response({"title": "Enter a title."}, status=400)
            bundle.title = title[:120]
        if "price" in data:
            try:
                amount = Decimal(str(data.get("price")))
            except Exception:
                return Response({"price": "Enter a price."}, status=400)
            if amount < 0:
                return Response({"price": "Price cannot be negative."}, status=400)
            bundle.price = amount
        if "is_active" in data:
            bundle.is_active = bool(data.get("is_active"))
        bundle.save()
        return Response(_bundle_payload(bundle))
