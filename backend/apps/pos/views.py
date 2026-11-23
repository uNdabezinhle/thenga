"""Staff till API. Shoppers never reach these routes."""
from __future__ import annotations

from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsStaffRole
from apps.platform.services import merchant_for


class IsTillOperator(IsStaffRole):
    """Sample staff, or a merchant owner running their own till."""

    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return True
        return merchant_for(getattr(request, "user", None)) is not None
from apps.catalogue.models import Product, ProductVariant
from apps.core.exceptions import RekaAPIException
from apps.pricing.services import money_str
from apps.promotions.models import Bundle
from apps.promotions.specials import live_unit_price

from .models import Store
from .services import (
    _allowed,
    _catalog_rows,
    _override,
    _store,
    available_units,
    close_drawer,
    drawer_state,
    move_drawer,
    open_drawer,
    sell,
    sync_sales,
)


def _fail(exc: RekaAPIException):
    return Response(
        {"error": {"code": exc.default_code, "message": str(exc.detail)}},
        status=exc.status_code,
    )


def _variant_row(store, variant, rows):
    override = _override(rows, variant_id=variant.pk)
    price = override if override is not None else live_unit_price(variant.product, variant)
    return {
        "kind": "variant",
        "variant_id": variant.pk,
        "name": variant.product.name,
        "sku": variant.sku,
        "label": variant.label,
        "barcode": variant.barcode or "",
        "unit_price": money_str(price),
        "available": available_units(store, variant),
        "sale_channel": variant.product.sale_channel,
    }


def _bundle_row(store, bundle, rows):
    components = list(bundle.items.select_related("variant", "variant__inventory"))
    available = None
    for component in components:
        have = available_units(store, component.variant)
        fits = have // component.quantity if component.quantity else 0
        available = fits if available is None else min(available, fits)
    override = _override(rows, bundle_id=bundle.pk)
    return {
        "kind": "bundle",
        "bundle_id": bundle.pk,
        "name": bundle.title,
        "sku": "",
        "label": "Bundle",
        "barcode": "",
        "unit_price": money_str(override if override is not None else bundle.price),
        "available": available or 0,
        "sale_channel": "pos",
    }


def _catalogue(store, query: str, user):
    rows = _catalog_rows(store)
    needle = (query or "").strip()
    variants = []
    if rows:
        ids = [row.variant_id for row in rows if row.variant_id]
        found = ProductVariant.objects.select_related("product", "inventory").filter(
            pk__in=ids, is_active=True, product__is_active=True
        )
    else:
        found = ProductVariant.objects.select_related("product", "inventory").filter(
            is_active=True,
            product__is_active=True,
            product__sale_channel__in=(Product.SaleChannel.BOTH, Product.SaleChannel.POS),
        )
    from apps.platform.services import variant_scope

    found = found.filter(variant_scope(user))
    if needle:
        found = found.filter(
            Q(sku__icontains=needle)
            | Q(label__icontains=needle)
            | Q(barcode__icontains=needle)
            | Q(product__name__icontains=needle)
            | Q(product__sku__icontains=needle)
        )
    for variant in found.order_by("product__name", "label")[:40]:
        variants.append(_variant_row(store, variant, rows))

    bundles = []
    if rows and any(row.bundle_id for row in rows):
        ids = [row.bundle_id for row in rows if row.bundle_id]
        found_bundles = Bundle.objects.filter(pk__in=ids, is_active=True)
    elif rows:
        found_bundles = Bundle.objects.none()
    else:
        found_bundles = Bundle.objects.filter(is_active=True)
    if needle:
        found_bundles = found_bundles.filter(title__icontains=needle)
    for bundle in found_bundles.order_by("title")[:20]:
        bundles.append(_bundle_row(store, bundle, rows))
    return variants, bundles


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsTillOperator])
def pos_stores(request):
    from .services import ensure_stores

    ensure_stores()
    stores = [
        {"code": store.code, "name": store.name, "sells_online": store.sells_online}
        for store in Store.objects.filter(is_active=True)
    ]
    return Response({"results": stores})


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsTillOperator])
def pos_catalog(request):
    try:
        store = _store(request.query_params.get("store"))
    except RekaAPIException as exc:
        return _fail(exc)
    variants, bundles = _catalogue(store, request.query_params.get("q") or "", request.user)
    return Response(
        {
            "store": {"code": store.code, "name": store.name, "sells_online": store.sells_online},
            "variants": variants,
            "bundles": bundles,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsTillOperator])
def pos_scan(request):
    try:
        store = _store(request.data.get("store_code") or request.data.get("store"))
    except RekaAPIException as exc:
        return _fail(exc)
    code = str(request.data.get("code") or "").strip()
    if not code:
        return Response(
            {"error": {"code": "validation_failed", "message": "Scan a code."}},
            status=400,
        )
    rows = _catalog_rows(store)
    variant = (
        ProductVariant.objects.select_related("product", "inventory")
        .filter(is_active=True, product__is_active=True)
        .filter(Q(barcode__iexact=code) | Q(sku__iexact=code))
        .first()
    )
    if variant is None:
        bundle = Bundle.objects.filter(title__iexact=code, is_active=True).first()
        if bundle and _allowed(rows, bundle_id=bundle.pk):
            return Response(_bundle_row(store, bundle, rows))
        return Response(
            {"error": {"code": "not_found", "message": "Nothing on the till matches that code."}},
            status=404,
        )
    if variant.product.sale_channel == Product.SaleChannel.ONLINE:
        return Response(
            {"error": {"code": "not_on_till", "message": "That product is not sold at the till."}},
            status=400,
        )
    if not _allowed(rows, variant_id=variant.pk):
        return Response(
            {"error": {"code": "not_in_store", "message": "That product is not in this store."}},
            status=400,
        )
    return Response(_variant_row(store, variant, rows))


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsTillOperator])
def pos_sale(request):
    try:
        body = sell(request.user, request.data)
    except RekaAPIException as exc:
        return _fail(exc)
    status = 200 if body.get("replayed") else 201
    return Response(body, status=status)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsTillOperator])
def pos_sync(request):
    try:
        results = sync_sales(request.user, request.data.get("sales") or [])
    except RekaAPIException as exc:
        return _fail(exc)
    return Response({"results": results})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsTillOperator])
def pos_drawer(request):
    try:
        if request.method == "GET":
            return Response(drawer_state(request.query_params.get("store")))
        action = str(request.data.get("action") or "open")
        store_code = request.data.get("store_code")
        if action == "close":
            session = close_drawer(
                request.user,
                store_code=store_code,
                closing_count=request.data.get("closing_count"),
            )
            return Response(
                {
                    "open": False,
                    "expected": money_str(session.expected),
                    "closing_count": money_str(session.closing_count),
                }
            )
        if action in ("pay_in", "pay_out"):
            movement = move_drawer(
                request.user,
                store_code=store_code,
                kind=action,
                amount=request.data.get("amount"),
                note=str(request.data.get("note") or ""),
            )
            return Response(drawer_state(store_code) | {"movement_id": movement.pk})
        open_drawer(
            request.user,
            store_code=store_code,
            opening_float=request.data.get("opening_float"),
        )
        return Response(drawer_state(store_code))
    except RekaAPIException as exc:
        return _fail(exc)
