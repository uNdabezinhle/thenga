from datetime import datetime
from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffRole
from apps.cart.models import Coupon
from apps.catalogue.models import Product
from apps.pricing.services import money_str

from apps.platform.services import has_addon, merchant_for

from .ads import public_ads, record_event
from .models import AdEvent, ShopAd
from .services import coupon_is_live


class PromotionListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        now = timezone.now()
        rows = []
        for coupon in Coupon.objects.all().order_by("code"):
            if not coupon_is_live(coupon, now):
                continue
            rows.append(
                {
                    "code": coupon.code,
                    "title": coupon.title or coupon.code,
                    "description": coupon.description,
                    "discount_type": coupon.discount_type,
                    "amount": money_str(coupon.amount),
                }
            )
        return Response({"results": rows})


class AdListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        placement = request.query_params.get("placement") or ShopAd.Placement.SHOP_TOP
        ads = list(public_ads(placement))
        for ad in ads:
            record_event(ad, AdEvent.Kind.IMPRESSION)
        slugs = [ad.product_slug for ad in ads if ad.product_slug]
        products = {
            product.slug: product.id
            for product in Product.objects.filter(slug__in=slugs, is_active=True)
        }
        return Response(
            {
                "results": [
                    {
                        "id": ad.id,
                        "title": ad.title,
                        "body": ad.body,
                        "placement": ad.placement,
                        "product_slug": ad.product_slug,
                        "product_id": products.get(ad.product_slug),
                    }
                    for ad in ads
                ]
            }
        )


def _coupon_payload(coupon: Coupon) -> dict:
    return {
        "code": coupon.code,
        "title": coupon.title,
        "description": coupon.description,
        "discount_type": coupon.discount_type,
        "amount": money_str(coupon.amount),
        "is_active": coupon.is_active,
        "starts_at": coupon.starts_at,
        "ends_at": coupon.ends_at,
    }


def _ad_payload(ad: ShopAd, products: dict) -> dict:
    return {
        "id": ad.id,
        "title": ad.title,
        "body": ad.body,
        "placement": ad.placement,
        "product_slug": ad.product_slug,
        "product_id": products.get(ad.product_slug),
        "is_active": ad.is_active,
        "sort_order": ad.sort_order,
    }


class StaffPromotionListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffRole]

    def get(self, request):
        rows = Coupon.objects.all().order_by("code")
        return Response({"results": [_coupon_payload(row) for row in rows]})


class StaffPromotionDetailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffRole]

    def patch(self, request, code):
        coupon = get_object_or_404(Coupon, code__iexact=code)
        data = request.data
        if "title" in data:
            coupon.title = str(data.get("title") or "")[:120]
        if "description" in data:
            coupon.description = str(data.get("description") or "")[:255]
        if "is_active" in data:
            coupon.is_active = bool(data.get("is_active"))
        if "amount" in data:
            try:
                amount = Decimal(str(data.get("amount")))
            except Exception:
                return Response({"amount": "Enter an amount."}, status=400)
            if amount < 0:
                return Response({"amount": "Amount cannot be negative."}, status=400)
            if coupon.discount_type == "percentage" and amount > Decimal("100"):
                return Response(
                    {"amount": "Percentage must be between 0 and 100."}, status=400
                )
            coupon.amount = amount
        for field in ("starts_at", "ends_at"):
            if field not in data:
                continue
            raw = data.get(field)
            if raw in (None, ""):
                setattr(coupon, field, None)
                continue
            try:
                parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                return Response({field: "Use an ISO date and time."}, status=400)
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            setattr(coupon, field, parsed)
        coupon.save()
        return Response(_coupon_payload(coupon))


class IsAdEditor(BasePermission):
    def has_permission(self, request, view):
        if IsStaffRole().has_permission(request, view):
            return True
        merchant = merchant_for(request.user)
        return merchant is not None and merchant.slug != "northbound"


class AdClickView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, pk):
        ad = get_object_or_404(ShopAd.objects.select_related("merchant"), pk=pk, is_active=True)
        if ad.source == "operated" and ad.merchant_id and not ad.merchant.operated_ads:
            return Response({"error": {"code": "not_found", "message": "Ad not found."}}, status=404)
        record_event(ad, AdEvent.Kind.CLICK)
        return Response({"id": ad.id, "recorded": "click"})


class StaffAdListView(APIView):
    permission_classes = [IsAuthenticated, IsAdEditor]

    def get(self, request):
        ads = list(ShopAd.objects.all())
        products = _product_ids(ads)
        return Response({"results": [_ad_payload(ad, products) for ad in ads]})

    def post(self, request):
        merchant = merchant_for(request.user)
        if not has_addon(merchant, "ads_self_serve"):
            return Response(
                {
                    "error": {
                        "code": "package_excluded",
                        "message": "Reka Ads self-serve is a paid extra. Operated ads stay with Reka.",
                    }
                },
                status=403,
            )
        title = str(request.data.get("title") or "").strip()
        if not title:
            return Response({"title": "Enter a title."}, status=400)
        ad = ShopAd.objects.create(
            title=title[:120],
            body=str(request.data.get("body") or "")[:255],
            product_slug=str(request.data.get("product_slug") or "")[:160],
            source="self_serve",
            merchant=None if merchant is None or merchant.slug == "northbound" else merchant,
        )
        return Response(_ad_payload(ad, _product_ids([ad])), status=201)


class StaffAdDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdEditor]

    def patch(self, request, pk):
        ad = get_object_or_404(ShopAd, pk=pk)
        data = request.data
        merchant = merchant_for(request.user)
        real = merchant is not None and merchant.slug != "northbound"
        if ad.source == "operated" and real:
            if set(data.keys()) - {"is_active"}:
                return Response(
                    {
                        "error": {
                            "code": "package_excluded",
                            "message": "Reka writes operated ads. You can turn the placement off.",
                        }
                    },
                    status=403,
                )
            if "is_active" in data:
                ad.is_active = bool(data.get("is_active"))
                ad.save(update_fields=["is_active"])
            return Response(_ad_payload(ad, _product_ids([ad])))
        if not has_addon(merchant, "ads_self_serve"):
            return Response(
                {
                    "error": {
                        "code": "package_excluded",
                        "message": "Reka Ads self-serve is a paid extra. Operated ads stay with Reka.",
                    }
                },
                status=403,
            )
        if "title" in data:
            title = str(data.get("title") or "").strip()
            if not title:
                return Response({"title": "Enter a title."}, status=400)
            ad.title = title[:120]
        if "body" in data:
            ad.body = str(data.get("body") or "")[:255]
        if "product_slug" in data:
            ad.product_slug = str(data.get("product_slug") or "")[:160]
        if "is_active" in data:
            ad.is_active = bool(data.get("is_active"))
        ad.save()
        products = _product_ids([ad])
        return Response(_ad_payload(ad, products))


def _product_ids(ads) -> dict:
    slugs = [ad.product_slug for ad in ads if ad.product_slug]
    return {
        product.slug: product.id
        for product in Product.objects.filter(slug__in=slugs, is_active=True)
    }
