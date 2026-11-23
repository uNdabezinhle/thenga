"""Staff order operations — list any order, process fulfilment."""
from __future__ import annotations

from decimal import Decimal

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsStaffRole
from apps.cart.models import ShippingEstimate
from apps.pricing.services import money_str

from .couriers import ensure_shipping_rates
from .models import Order, Shipment, ShippingRate
from .serializers import OrderSerializer
from .services import OrderError, advance_order, apply_courier_status, book_shipment


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStaffRole])
def staff_order_list(request):
    """GET /api/v1/orders/staff/ — all orders (ops)."""
    status_filter = request.query_params.get("status")
    channel = request.query_params.get("channel")
    qs = Order.objects.prefetch_related(
        "items", "events", "shipments__events", "payments"
    ).order_by(
        "-placed_at"
    )
    if channel == "all":
        pass
    elif channel:
        qs = qs.filter(channel=channel)
    else:
        qs = qs.exclude(channel=Order.Channel.POS)
    if status_filter:
        qs = qs.filter(status=status_filter)
    qs = qs[:100]
    return Response({"results": OrderSerializer(qs, many=True).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStaffRole])
def staff_order_detail(request, reference):
    try:
        order = Order.objects.prefetch_related(
            "items", "events", "shipments__events", "payments"
        ).get(reference=reference)
    except Order.DoesNotExist:
        return Response(
            {
                "error": {
                    "code": "not_found",
                    "message": "Order not found.",
                    "request_id": getattr(request, "request_id", "-"),
                }
            },
            status=404,
        )
    return Response(OrderSerializer(order).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsStaffRole])
def staff_advance(request, reference):
    try:
        order = Order.objects.get(reference=reference)
    except Order.DoesNotExist:
        return Response(
            {
                "error": {
                    "code": "not_found",
                    "message": "Order not found.",
                    "request_id": getattr(request, "request_id", "-"),
                }
            },
            status=404,
        )
    try:
        order = advance_order(order, actor=request.user)
    except OrderError as exc:
        return Response(
            {
                "error": {
                    "code": exc.default_code,
                    "message": str(exc.detail),
                    "request_id": getattr(request, "request_id", "-"),
                }
            },
            status=409,
        )
    return Response(OrderSerializer(order).data)


def _missing(request):
    return Response(
        {
            "error": {
                "code": "not_found",
                "message": "Order not found.",
                "request_id": getattr(request, "request_id", "-"),
            }
        },
        status=404,
    )


def _conflict(request, exc: OrderError):
    return Response(
        {
            "error": {
                "code": exc.default_code,
                "message": str(exc.detail),
                "request_id": getattr(request, "request_id", "-"),
            }
        },
        status=409,
    )


def _with_shipment(order: Order) -> Order:
    return Order.objects.prefetch_related(
        "items", "events", "shipments__events", "payments"
    ).get(pk=order.pk)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsStaffRole])
def staff_dispatch(request, reference):
    """Book the sandbox courier for a packed order."""
    try:
        order = Order.objects.get(reference=reference)
    except Order.DoesNotExist:
        return _missing(request)
    try:
        order = book_shipment(order, actor=request.user)
    except OrderError as exc:
        return _conflict(request, exc)
    return Response(OrderSerializer(_with_shipment(order)).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsStaffRole])
def staff_courier(request, reference):
    """Move a booked shipment to in_transit or delivered."""
    try:
        order = Order.objects.get(reference=reference)
    except Order.DoesNotExist:
        return _missing(request)
    status = str(request.data.get("status") or "")
    if status not in (Shipment.Status.IN_TRANSIT, Shipment.Status.DELIVERED):
        return _conflict(
            request,
            OrderError(
                "Courier status must be in_transit or delivered.",
                code="invalid_transition",
            ),
        )
    try:
        order = apply_courier_status(order, status, actor=request.user)
    except OrderError as exc:
        return _conflict(request, exc)
    return Response(OrderSerializer(_with_shipment(order)).data)


def _rate_payload(rate: ShippingRate) -> dict:
    return {
        "id": rate.id,
        "method_name": rate.method_name,
        "price": money_str(rate.price),
        "estimated_days": rate.estimated_days,
        "sort_order": rate.sort_order,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStaffRole])
def staff_shipping_rates(request):
    rows = ensure_shipping_rates()
    return Response({"results": [_rate_payload(row) for row in rows]})


@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsStaffRole])
def staff_shipping_rate_update(request, pk):
    try:
        rate = ShippingRate.objects.get(pk=pk)
    except ShippingRate.DoesNotExist:
        return _missing(request)
    price = request.data.get("price", None)
    days = request.data.get("estimated_days", None)
    if price is None and days is None:
        return Response({"price": "Send a price or a day label."}, status=400)
    if price is not None:
        try:
            amount = Decimal(str(price))
        except Exception:
            return Response({"price": "Enter a price in rand."}, status=400)
        if amount < 0:
            return Response({"price": "Price cannot be negative."}, status=400)
        rate.price = amount
    if days is not None:
        label = str(days).strip()
        if not label:
            return Response({"estimated_days": "Enter a day label."}, status=400)
        rate.estimated_days = label[:64]
    rate.save()
    ShippingEstimate.objects.filter(
        cart__is_active=True, method_name=rate.method_name
    ).update(price=rate.price, estimated_days=rate.estimated_days)
    return Response(_rate_payload(rate))
