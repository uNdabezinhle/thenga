from __future__ import annotations

import difflib

from django.db.models import Avg, Case, Count, IntegerField, Prefetch, Q, When
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Brand, Category, Product, ProductVariant, Review
from .serializers import (
    BrandSerializer,
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ReviewSerializer,
)


def _match_score(query: str, text: str) -> float:
    left = query.lower().strip()
    right = (text or "").lower()
    if not left or not right:
        return 0.0
    if left in right:
        return 1.0
    best = difflib.SequenceMatcher(None, left, right).ratio()
    for word in right.split():
        best = max(best, difflib.SequenceMatcher(None, left, word).ratio())
    return best


def _xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"


class BrandViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Brand.objects.filter(is_active=True)
    serializer_class = BrandSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    filterset_fields = []
    search_fields = ["name", "description", "sku", "brand__name"]
    ordering_fields = ["base_price", "created_at", "name"]
    ordering = ["-created_at"]
    pagination_class = None  # return full catalogue for the demo client

    def get_queryset(self):
        qs = (
            Product.objects.filter(is_active=True).exclude(
                sale_channel=Product.SaleChannel.POS
            )
            .select_related("brand", "category")
            .prefetch_related(
                Prefetch(
                    "variants",
                    queryset=ProductVariant.objects.filter(is_active=True).select_related(
                        "inventory"
                    ),
                ),
                "attributes",
            )
            .annotate(
                avg_rating=Avg(
                    "reviews__rating", filter=Q(reviews__is_approved=True)
                ),
                review_count=Count(
                    "reviews", filter=Q(reviews__is_approved=True)
                ),
            )
        )

        params = self.request.query_params
        from apps.platform.catalog import SAMPLE_SLUG
        from apps.platform.services import public_product_scope, shop_is_public

        merchant_slug = (params.get("merchant") or SAMPLE_SLUG).strip().lower() or SAMPLE_SLUG
        if not shop_is_public(merchant_slug):
            qs = qs.none()
        else:
            qs = qs.filter(public_product_scope(merchant_slug))
        cat = params.get("category")
        if cat and cat != "all":
            qs = qs.filter(Q(category__slug=cat) | Q(category__name__iexact=cat))

        brand = params.get("brand")
        if brand:
            qs = qs.filter(brand__slug=brand)

        price_min = params.get("price_min")
        price_max = params.get("price_max")
        if price_min:
            qs = qs.filter(base_price__gte=price_min)
        if price_max:
            qs = qs.filter(base_price__lte=price_max)

        sort = params.get("sort")
        if sort == "low" or sort == "price":
            qs = qs.order_by("base_price")
        elif sort in ("high", "-price"):
            qs = qs.order_by("-base_price")
        elif sort in ("rated", "-rating"):
            qs = qs.order_by("-avg_rating")
        elif sort == "recency" or sort == "-created_at":
            qs = qs.order_by("-created_at")

        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProductDetailSerializer
        return ProductListSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        q = (request.query_params.get("q") or request.query_params.get("search") or "").strip()
        if q:
            queryset = self._search(queryset, q, request.query_params.get("sort"))
        ser = self.get_serializer(queryset, many=True)
        return Response({"results": ser.data, "next": None, "previous": None})

    def _search(self, qs, q, sort):
        strict = qs.filter(
            Q(name__icontains=q)
            | Q(description__icontains=q)
            | Q(brand__name__icontains=q)
            | Q(sku__icontains=q)
        )
        if strict.exists():
            return strict
        scored = []
        for product in qs.select_related("brand"):
            texts = [product.name, product.sku, product.description or ""]
            if product.brand_id:
                texts.append(product.brand.name)
            score = max(_match_score(q, text) for text in texts)
            if score >= 0.62:
                scored.append((score, product.pk))
        if not scored:
            return qs.none()
        scored.sort(reverse=True)
        if sort:
            return qs.filter(pk__in=[pk for _, pk in scored])
        order = [pk for _, pk in scored]
        preserved = Case(
            *[When(pk=pk, then=pos) for pos, pk in enumerate(order)],
            output_field=IntegerField(),
        )
        return qs.filter(pk__in=order).order_by(preserved)

    @action(detail=True, methods=["get"], url_path="image")
    def image(self, request, pk=None):
        """Generated product art. Real ProductImage rows are not seeded."""
        product = self.get_object()
        hue = int(product.hue or 150)
        label = (product.name or "Northbound")[:28]
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">
<rect width="400" height="300" fill="hsl({hue},34%,93%)"/>
<path d="M20 230 L90 150 L140 190 L210 90 L280 170 L380 70 L380 280 L20 280 Z" fill="hsl({hue},42%,32%)"/>
<path d="M20 250 L120 190 L190 220 L260 150 L380 210 L380 280 L20 280 Z" fill="hsl({hue},38%,22%)"/>
<text x="24" y="40" font-family="sans-serif" font-size="16" fill="hsl({hue},40%,18%)">{_xml(label)}</text>
</svg>"""
        return HttpResponse(svg, content_type="image/svg+xml")

    @action(detail=True, methods=["get", "post"], url_path="reviews")
    def reviews(self, request, pk=None):
        product = self.get_object()
        if request.method == "POST":
            if not request.user.is_authenticated:
                return Response(
                    {"error": {"code": "authentication_failed", "message": "Sign in to review."}},
                    status=401,
                )
            try:
                rating = int(request.data.get("rating"))
            except (TypeError, ValueError):
                rating = 0
            body = str(request.data.get("body") or "").strip()
            from apps.orders.services import OrderError
            from apps.platform.services import require_addon

            try:
                require_addon(product.merchant, "reviews")
            except OrderError as exc:
                return Response(
                    {"error": {"code": exc.default_code, "message": str(exc.detail)}},
                    status=exc.status_code,
                )
            if rating < 1 or rating > 5 or not body:
                return Response(
                    {"rating": "Choose 1 to 5 stars and write a short review."},
                    status=400,
                )
            who = ""
            profile = getattr(request.user, "profile", None)
            if profile is not None:
                who = profile.display_name
            review, _ = Review.objects.update_or_create(
                product=product,
                user=request.user,
                defaults={
                    "rating": rating,
                    "body": body[:2000],
                    "title": "",
                    "author_display": who or request.user.username,
                    "is_approved": True,
                },
            )
            return Response(ReviewSerializer(review).data)
        qs = product.reviews.filter(is_approved=True)
        return Response(ReviewSerializer(qs, many=True).data)
