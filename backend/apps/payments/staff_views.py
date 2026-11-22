"""Staff payment/refund operations."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsStaffRole
from apps.orders.models import Order, Refund
from apps.pricing.services import money_str

from .refunds import RefundError, issue_refund


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsStaffRole])
def create_refund(request):
    """
    POST /api/v1/payments/refunds/
    { "order_reference": "NB-…", "amount": "50.00"|null, "reason": "…" }
    Omit amount for full remaining balance.
    """
    reference = request.data.get("order_reference") or request.data.get("reference")
    if not reference:
        return Response(
            {
                "error": {
                    "code": "validation_failed",
                    "message": "order_reference is required.",
                    "request_id": getattr(request, "request_id", "-"),
                }
            },
            status=400,
        )
    try:
        order = Order.objects.prefetch_related("payments", "items").get(
            reference=reference
        )
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

    raw_amount = request.data.get("amount", None)
    amount = None
    if raw_amount is not None and raw_amount != "":
        try:
            amount = Decimal(str(raw_amount))
        except (InvalidOperation, TypeError):
            return Response(
                {
                    "error": {
                        "code": "validation_failed",
                        "message": "Invalid amount.",
                        "field": "amount",
                        "request_id": getattr(request, "request_id", "-"),
                    }
                },
                status=400,
            )

    idem = request.headers.get("Idempotency-Key") or request.data.get("idempotency_key")
    try:
        refund = issue_refund(
            order=order,
            amount=amount,
            reason=request.data.get("reason", ""),
            staff_user=request.user,
            idempotency_key=idem,
        )
    except RefundError as exc:
        return Response(
            {
                "error": {
                    "code": exc.default_code,
                    "message": str(exc.detail),
                    "details": getattr(exc, "details", None),
                    "request_id": getattr(request, "request_id", "-"),
                }
            },
            status=exc.status_code if exc.status_code != 400 else 409,
        )

    order.refresh_from_db()
    payment = refund.payment
    return Response(
        {
            "id": refund.id,
            "provider_reference": refund.provider_reference,
            "amount": money_str(refund.amount),
            "currency": payment.currency,
            "reason": refund.reason,
            "order_reference": order.reference,
            "order_status": order.status,
            "payment_status": payment.status,
            "created_at": refund.created_at.isoformat().replace("+00:00", "Z"),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStaffRole])
def list_refunds(request):
    qs = Refund.objects.select_related(
        "payment", "payment__order", "created_by"
    ).order_by("-created_at")[:100]
    data = [
        {
            "id": r.id,
            "provider_reference": r.provider_reference,
            "amount": money_str(r.amount),
            "reason": r.reason,
            "order_reference": r.payment.order.reference,
            "created_by": r.created_by.email if r.created_by else None,
            "created_at": r.created_at.isoformat().replace("+00:00", "Z"),
        }
        for r in qs
    ]
    return Response({"results": data})


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStaffRole])
def reconciliation(request):
    """
    GET /api/v1/payments/reconciliation/?date=YYYY-MM-DD
    Daily payment reconciliation report (REKA-FR-PAY-007).
    """
    from datetime import date as date_cls

    from .reconciliation import build_reconciliation

    raw = request.query_params.get("date")
    day = None
    if raw:
        try:
            day = date_cls.fromisoformat(raw)
        except ValueError:
            return Response(
                {
                    "error": {
                        "code": "validation_failed",
                        "message": "date must be YYYY-MM-DD.",
                        "field": "date",
                        "request_id": getattr(request, "request_id", "-"),
                    }
                },
                status=400,
            )
    report = build_reconciliation(day)
    return Response(report.as_dict())
