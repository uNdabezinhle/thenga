from __future__ import annotations

from django.http import HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.cart.services import get_or_create_cart

from .invoices import render_invoice_html
from .models import Address, Order
from .serializers import AddressSerializer, OrderSerializer, PlaceOrderSerializer
from .services import advance_order, place_order


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]
    queryset = Address.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Address.objects.none()
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"
    lookup_value_regex = r"[^/]+"
    pagination_class = None
    queryset = Order.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return (
            Order.objects.filter(user=self.request.user)
            .prefetch_related("items", "events", "shipments__events")
        )

    def create(self, request):
        ser = PlaceOrderSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cart = get_or_create_cart(request)
        address = None
        address_id = ser.validated_data.get("address_id")
        if address_id:
            address = Address.objects.filter(user=request.user, pk=address_id).first()
        address_text = ser.validated_data.get("address") or ""
        if not address_text and address:
            address_text = address.as_single_line()
        if not address_text:
            profile = getattr(request.user, "profile", None)
            address_text = (profile.address if profile and profile.address else "") or (
                "14 Harbour Lane, Cape Town 8001"
            )

        idem = request.headers.get("Idempotency-Key")
        order, payment, redirect_url = place_order(
            user=request.user,
            cart=cart,
            payment_method=ser.validated_data["payment_method"],
            address_text=address_text,
            address=address,
            idempotency_key=idem,
            return_url=ser.validated_data.get("return_url", ""),
        )
        order = self.get_queryset().get(pk=order.pk)
        payload = OrderSerializer(order).data
        payload["payment"] = {
            "status": payment.status if payment else None,
            "provider": payment.provider if payment else None,
            "provider_reference": payment.provider_reference if payment else None,
            "redirect_url": redirect_url or "",
        }
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="tracking")
    def tracking(self, request, reference=None):
        order = self.get_object()
        stages = [
            "Order placed",
            "Payment confirmed",
            "Packed",
            "Out for delivery",
            "Delivered",
        ]
        return Response(
            {
                "reference": order.reference,
                "status": order.status,
                "stage": order.tracking_stage,
                "stages": stages,
                "events": [
                    {
                        "to_status": e.to_status,
                        "note": e.note,
                        "created_at": e.created_at.isoformat().replace("+00:00", "Z"),
                    }
                    for e in order.events.all()
                ],
            }
        )

    @action(detail=True, methods=["post"], url_path="advance")
    def advance(self, request, reference=None):
        """Demo helper: advance fulfilment stage (simulates webhook / staff action)."""
        order = self.get_object()
        order = advance_order(order, actor=request.user)
        order = self.get_queryset().get(pk=order.pk)
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["get"], url_path="invoice")
    def invoice(self, request, reference=None):
        """Tax invoice HTML — REKA-FR-ORD-013. Staff can open a counter receipt."""
        from apps.accounts.permissions import IsStaffRole

        if IsStaffRole().has_permission(request, self):
            order = (
                Order.objects.filter(reference=reference)
                .prefetch_related("items")
                .select_related("user")
                .first()
            )
            if order is None:
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
        else:
            order = self.get_object()
        if order.status in (
            Order.Status.AWAITING_PAYMENT,
            Order.Status.CANCELLED,
        ):
            return Response(
                {
                    "error": {
                        "code": "invoice_unavailable",
                        "message": "An invoice is available after payment is confirmed.",
                        "request_id": getattr(request, "request_id", "-"),
                    }
                },
                status=409,
            )
        from .invoices import invoice_payload

        if request.query_params.get("format") == "json":
            return Response(invoice_payload(order))
        html = render_invoice_html(order)
        return HttpResponse(html, content_type="text/html; charset=utf-8")

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, reference=None):
        from apps.core.exceptions import RekaAPIException

        from .services import cancel_order

        order = self.get_object()
        try:
            order = cancel_order(
                order, actor=request.user, note="Cancelled by customer"
            )
        except RekaAPIException as exc:
            return Response(
                {
                    "error": {
                        "code": exc.default_code,
                        "message": str(exc.detail),
                        "request_id": getattr(request, "request_id", "-"),
                    }
                },
                status=exc.status_code if exc.status_code != 400 else 409,
            )
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["get"], url_path="cooling-off")
    def cooling_off_info(self, request, reference=None):
        """GET eligibility for ECTA s44 cooling-off."""
        from .cooling_off import cooling_off_status

        order = self.get_object()
        s = cooling_off_status(order)
        return Response(
            {
                "reference": order.reference,
                "eligible": s.eligible,
                "reason": s.reason,
                "deadline": s.deadline,
                "days_remaining": s.days_remaining,
                "excluded_items": s.excluded_items,
                "cooling_off_days": 7,
            }
        )

    @action(detail=True, methods=["post"], url_path="cooling-off/exercise")
    def cooling_off_exercise(self, request, reference=None):
        """POST — exercise 7-day cooling-off; issues full refund (REKA-FR-ORD-011)."""
        from .cooling_off import CoolingOffError, exercise_cooling_off

        order = self.get_object()
        try:
            order = exercise_cooling_off(
                order,
                user=request.user,
                reason=request.data.get("reason", ""),
            )
        except CoolingOffError as exc:
            code = getattr(exc, "default_code", "cooling_off_unavailable")
            http = 404 if code == "not_found" else 409
            return Response(
                {
                    "error": {
                        "code": code,
                        "message": str(exc.detail),
                        "details": getattr(exc, "details", None),
                        "request_id": getattr(request, "request_id", "-"),
                    }
                },
                status=http,
            )
        order = self.get_queryset().get(pk=order.pk)
        return Response(OrderSerializer(order).data)
