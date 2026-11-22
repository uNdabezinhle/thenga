"""Staff order operations — list any order, process fulfilment."""
from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsStaffRole

from .models import Order
from .serializers import OrderSerializer
from .services import advance_order


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStaffRole])
def staff_order_list(request):
    """GET /api/v1/orders/staff/ — all orders (ops)."""
    status_filter = request.query_params.get("status")
    qs = Order.objects.prefetch_related("items", "events", "shipments", "payments").order_by(
        "-placed_at"
    )
    if status_filter:
        qs = qs.filter(status=status_filter)
    qs = qs[:100]
    return Response({"results": OrderSerializer(qs, many=True).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStaffRole])
def staff_order_detail(request, reference):
    try:
        order = Order.objects.prefetch_related(
            "items", "events", "shipments", "payments"
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
    from apps.orders.services import OrderError

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
