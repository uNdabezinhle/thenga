from __future__ import annotations

import json
from decimal import Decimal

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.orders.models import Order, Payment
from apps.pricing.services import money_str

from .providers import PayfastProvider, SandboxProvider
from .services import (
    PaymentError,
    confirm_payment_from_webhook,
    initiate_payment,
    process_sandbox_webhook,
    simulate_sandbox_success,
)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def initiate(request):
    """Start payment for an order awaiting payment."""
    reference = request.data.get("order_reference") or request.data.get("reference")
    if not reference:
        return Response(
            {"error": {"code": "validation_failed", "message": "order_reference required.", "request_id": getattr(request, "request_id", "-")}},
            status=400,
        )
    try:
        order = Order.objects.get(reference=reference, user=request.user)
    except Order.DoesNotExist:
        return Response(
            {"error": {"code": "not_found", "message": "Order not found.", "request_id": getattr(request, "request_id", "-")}},
            status=404,
        )
    try:
        payment = initiate_payment(
            order,
            payment_method=order.payment_method or "card",
            return_url=request.data.get("return_url", ""),
        )
    except PaymentError as exc:
        return Response(
            {
                "error": {
                    "code": exc.default_code,
                    "message": str(exc.detail),
                    "request_id": getattr(request, "request_id", "-"),
                }
            },
            status=exc.status_code,
        )
    return Response(
        {
            "payment_id": payment.id,
            "provider": payment.provider,
            "provider_reference": payment.provider_reference,
            "status": payment.status,
            "amount": money_str(payment.amount),
            "currency": payment.currency,
            "redirect_url": getattr(payment, "_redirect_url", "") or "",
            "form_action": getattr(payment, "_form_action", "") or "",
            "form_fields": getattr(payment, "_form_fields", None) or {},
        },
        status=status.HTTP_201_CREATED,
    )


@csrf_exempt
@require_POST
def sandbox_webhook(request):
    """Provider webhook — signature verified, idempotent (REKA-FR-PAY-003/004)."""
    sig = request.headers.get("X-Sandbox-Signature") or request.META.get(
        "HTTP_X_SANDBOX_SIGNATURE"
    )
    try:
        payment = process_sandbox_webhook(request.body, sig)
    except PaymentError as exc:
        return HttpResponse(
            json.dumps({"error": {"code": exc.default_code, "message": str(exc.detail)}}),
            status=exc.status_code,
            content_type="application/json",
        )
    return HttpResponse(
        json.dumps(
            {
                "ok": True,
                "payment_status": payment.status,
                "order_reference": payment.order.reference,
                "order_status": payment.order.status,
            }
        ),
        status=200,
        content_type="application/json",
    )


@require_GET
def sandbox_checkout_page(request):
    """Simulated hosted payment page (SAQ A — no card fields posted to app logic)."""
    ref = request.GET.get("ref", "")
    order = request.GET.get("order", "")
    amount = request.GET.get("amount", "0.00")
    currency = request.GET.get("currency", "ZAR")
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Sandbox Checkout</title>
<style>
body{{font-family:system-ui,sans-serif;background:#0E2A22;color:#F3F4EF;display:grid;place-items:center;min-height:100vh;margin:0}}
.card{{background:#16362B;border-radius:16px;padding:28px;max-width:380px;width:90%;box-shadow:0 20px 50px rgba(0,0,0,.4)}}
h1{{font-size:1.25rem;margin:0 0 8px}}
.muted{{color:#8FA396;font-size:.9rem;line-height:1.5}}
.mono{{font-family:ui-monospace,monospace}}
.amt{{font-size:1.8rem;font-weight:700;margin:18px 0;color:#C8F751}}
button{{width:100%;padding:14px;border:0;border-radius:12px;background:#C8F751;color:#0E2A22;font-weight:600;font-size:1rem;cursor:pointer}}
button:disabled{{opacity:.5}}
.fail{{background:transparent;color:#C8F751;border:1px solid #3a5548;margin-top:8px}}
#msg{{margin-top:14px;font-size:.85rem;color:#8FA396}}
</style></head><body>
<div class="card">
  <h1>Sandbox hosted checkout</h1>
  <p class="muted">PCI SAQ A simulation — card data never reaches Reka.
  Order <span class="mono">{order}</span></p>
  <div class="amt mono">{currency} {amount}</div>
  <button id="pay">Pay with test card ···· 4242</button>
  <button class="fail" id="fail">Simulate failure</button>
  <p id="msg"></p>
</div>
<script>
const ref = {json.dumps(ref)};
const amount = {json.dumps(amount)};
async function send(status) {{
  document.getElementById('pay').disabled = true;
  document.getElementById('fail').disabled = true;
  document.getElementById('msg').textContent = 'Confirming…';
  const body = JSON.stringify({{
    provider_reference: ref,
    status: status,
    amount: amount,
    card_last4: status === 'succeeded' ? '4242' : '',
    card_brand: status === 'succeeded' ? 'Visa' : '',
    event_id: crypto.randomUUID()
  }});
  // Signature is computed server-side for the simulate endpoint in demo;
  // the real path is POST /webhooks/sandbox/ with X-Sandbox-Signature.
  const r = await fetch('/api/v1/payments/sandbox/simulate/', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: body
  }});
  const data = await r.json();
  if (r.ok) {{
    document.getElementById('msg').textContent = status === 'succeeded'
      ? 'Paid. You can close this window and return to the app.'
      : 'Payment failed (simulated).';
  }} else {{
    document.getElementById('msg').textContent = (data.error && data.error.message) || 'Error';
    document.getElementById('pay').disabled = false;
    document.getElementById('fail').disabled = false;
  }}
}}
document.getElementById('pay').onclick = () => send('succeeded');
document.getElementById('fail').onclick = () => send('failed');
</script>
</body></html>"""
    return HttpResponse(html)


@csrf_exempt
@require_POST
def sandbox_simulate(request):
    """
    Hosted page posts here. We sign the body ourselves and run the same
    webhook path — so confirmation still goes through signature verification.
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
        ref = data["provider_reference"]
        payment = Payment.objects.select_related("order").get(provider_reference=ref)
    except (KeyError, json.JSONDecodeError, Payment.DoesNotExist):
        return HttpResponse(
            json.dumps({"error": {"code": "not_found", "message": "Payment not found."}}),
            status=404,
            content_type="application/json",
        )

    if data.get("status") in ("failed", "fail"):
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status"])
        return HttpResponse(
            json.dumps({"ok": True, "payment_status": "failed"}),
            content_type="application/json",
        )

    try:
        payment = simulate_sandbox_success(payment)
    except PaymentError as exc:
        return HttpResponse(
            json.dumps({"error": {"code": exc.default_code, "message": str(exc.detail)}}),
            status=400,
            content_type="application/json",
        )
    return HttpResponse(
        json.dumps(
            {
                "ok": True,
                "payment_status": payment.status,
                "order_reference": payment.order.reference,
                "order_status": payment.order.status,
            }
        ),
        content_type="application/json",
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def complete_sandbox(request):
    """Authenticated shortcut for the mobile/web client to finish sandbox pay."""
    reference = request.data.get("order_reference") or request.data.get("reference")
    try:
        order = Order.objects.get(reference=reference, user=request.user)
    except Order.DoesNotExist:
        return Response(
            {"error": {"code": "not_found", "message": "Order not found.", "request_id": getattr(request, "request_id", "-")}},
            status=404,
        )
    payment = order.payments.filter(status=Payment.Status.PENDING).first()
    if not payment:
        payment = order.payments.order_by("-created_at").first()
    if not payment:
        return Response(
            {"error": {"code": "not_found", "message": "No payment for order.", "request_id": getattr(request, "request_id", "-")}},
            status=404,
        )
    if payment.status == Payment.Status.SUCCEEDED:
        return Response(
            {
                "payment_status": payment.status,
                "order_reference": order.reference,
                "order_status": order.status,
            }
        )
    payment = simulate_sandbox_success(payment)
    order.refresh_from_db()
    return Response(
        {
            "payment_status": payment.status,
            "order_reference": order.reference,
            "order_status": order.status,
        }
    )


@require_GET
def payfast_redirect(request):
    """Auto-post HTML form to Payfast hosted checkout (SAQ A)."""
    from html import escape

    order_ref = request.GET.get("order", "")
    try:
        order = Order.objects.get(reference=order_ref)
        payment = order.payments.filter(status=Payment.Status.PENDING).latest("created_at")
    except (Order.DoesNotExist, Payment.DoesNotExist):
        return HttpResponse("Payment not found.", status=404)

    from apps.payments.providers import payfast_for_order

    provider = payfast_for_order(order)
    session = provider.create_checkout(
        order_reference=order.reference,
        amount=payment.amount,
        currency=payment.currency,
        return_url=request.build_absolute_uri("/"),
        cancel_url=request.build_absolute_uri("/"),
        idempotency_key=payment.idempotency_key,
    )
    # Keep payment on payfast provider ref
    if payment.provider != "payfast":
        payment.provider = session.provider
        payment.provider_reference = session.provider_reference
        payment.save(update_fields=["provider", "provider_reference"])

    inputs = "\n".join(
        f'<input type="hidden" name="{escape(k)}" value="{escape(str(v))}">'
        for k, v in session.form_fields.items()
    )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Redirecting to Payfast…</title></head>
<body style="font-family:system-ui;display:grid;place-items:center;min-height:100vh;background:#0E2A22;color:#F3F4EF">
  <div style="text-align:center">
    <p>Redirecting to secure Payfast checkout…</p>
    <form id="pf" method="post" action="{escape(session.form_action)}">
      {inputs}
      <noscript><button type="submit">Continue to Payfast</button></noscript>
    </form>
  </div>
  <script>document.getElementById('pf').submit();</script>
</body></html>"""
    return HttpResponse(html)


@csrf_exempt
@require_POST
def payfast_itn(request):
    """Payfast Instant Transaction Notification — signature verified (REKA-FR-PAY-003)."""
    from apps.payments.providers import payfast_for_order

    data = PayfastProvider().parse_itn(request.body)
    order = Order.objects.filter(reference=data.get("m_payment_id") or "").select_related("merchant").first()
    provider = payfast_for_order(order) if order is not None else PayfastProvider()
    if not provider.verify_webhook(request.body, None):
        return HttpResponse("Invalid signature", status=400)
    payment_status = (data.get("payment_status") or "").upper()
    m_payment_id = data.get("m_payment_id") or ""
    pf_payment_id = data.get("pf_payment_id") or ""
    amount = data.get("amount_gross") or data.get("amount") 

    status_map = {
        "COMPLETE": "succeeded",
        "CANCELLED": "failed",
        "FAILED": "failed",
    }
    mapped = status_map.get(payment_status, "failed")

    try:
        payment = confirm_payment_from_webhook(
            provider_reference=m_payment_id,
            status=mapped,
            amount=Decimal(str(amount)) if amount else None,
            card_last4="",
            card_brand="",
            event_id=pf_payment_id or None,
        )
    except PaymentError as exc:
        # Payfast expects 200 for acknowledged noise sometimes; we 400 on hard errors
        return HttpResponse(str(exc.detail), status=400)

    # Payfast wants plain 200 OK body
    return HttpResponse("OK", status=200)
