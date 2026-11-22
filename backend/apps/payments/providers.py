"""Payment providers — ADR-0011 (PCI DSS SAQ A).

Card data never touches Reka. Hosted checkout / ITN only.
Default provider: sandbox. Optional: Payfast (ZA) when credentials set.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol
from urllib.parse import urlencode

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class CheckoutSession:
    provider: str
    provider_reference: str
    redirect_url: str
    amount: Decimal
    currency: str
    # Optional: for providers that need a POST form instead of GET redirect
    form_fields: dict[str, str] = field(default_factory=dict)
    form_action: str = ""


class PaymentProvider(Protocol):
    name: str

    def create_checkout(
        self,
        *,
        order_reference: str,
        amount: Decimal,
        currency: str,
        return_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> CheckoutSession: ...

    def verify_webhook(self, payload: bytes, signature: str | None) -> bool: ...


class SandboxProvider:
    """Local/dev provider. No external network. Hosted page is on our API."""

    name = "sandbox"

    def create_checkout(
        self,
        *,
        order_reference: str,
        amount: Decimal,
        currency: str,
        return_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> CheckoutSession:
        ref = f"SANDBOX-{uuid.uuid4().hex[:12].upper()}"
        base = getattr(settings, "PUBLIC_API_BASE", "http://127.0.0.1:8000").rstrip("/")
        redirect = (
            f"{base}/api/v1/payments/sandbox/checkout/"
            f"?ref={ref}&order={order_reference}&amount={amount:.2f}&currency={currency}"
        )
        return CheckoutSession(
            provider=self.name,
            provider_reference=ref,
            redirect_url=redirect,
            amount=amount,
            currency=currency,
        )

    def verify_webhook(self, payload: bytes, signature: str | None) -> bool:
        if not signature:
            return False
        secret = settings.PAYMENT_WEBHOOK_SECRET.encode("utf-8")
        expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def sign(self, payload: bytes) -> str:
        secret = settings.PAYMENT_WEBHOOK_SECRET.encode("utf-8")
        return hmac.new(secret, payload, hashlib.sha256).hexdigest()


class CODProvider:
    """Cash on delivery — no external capture."""

    name = "cod"

    def create_checkout(self, **kwargs) -> CheckoutSession:
        ref = f"COD-{uuid.uuid4().hex[:10].upper()}"
        return CheckoutSession(
            provider=self.name,
            provider_reference=ref,
            redirect_url="",
            amount=kwargs["amount"],
            currency=kwargs["currency"],
        )

    def verify_webhook(self, payload: bytes, signature: str | None) -> bool:
        return False


# --- Payfast (South Africa) -------------------------------------------------

# Field order for signature generation (Payfast docs)
_PAYFAST_SIGN_KEYS = (
    "merchant_id",
    "merchant_key",
    "return_url",
    "cancel_url",
    "notify_url",
    "name_first",
    "name_last",
    "email_address",
    "cell_number",
    "m_payment_id",
    "amount",
    "item_name",
    "item_description",
    "custom_int1",
    "custom_str1",
    "custom_str2",
    "custom_str3",
    "custom_str4",
    "custom_str5",
    "email_confirmation",
    "confirmation_address",
    "payment_method",
)


def payfast_signature(data: dict[str, str], passphrase: str = "") -> str:
    """MD5 signature over non-empty fields in Payfast attribute order + passphrase."""
    pairs = []
    for key in _PAYFAST_SIGN_KEYS:
        val = data.get(key)
        if val is None or val == "":
            continue
        pairs.append(f"{key}={urlencode({key: str(val)}).split('=', 1)[1]}")
    # Also include any remaining keys that Payfast may send on ITN (sorted)
    extras = sorted(
        k
        for k in data.keys()
        if k not in _PAYFAST_SIGN_KEYS and k != "signature" and data.get(k) not in (None, "")
    )
    for key in extras:
        pairs.append(f"{key}={urlencode({key: str(data[key])}).split('=', 1)[1]}")
    param_string = "&".join(pairs)
    if passphrase:
        param_string = f"{param_string}&passphrase={urlencode({'p': passphrase}).split('=', 1)[1]}"
    return hashlib.md5(param_string.encode("utf-8")).hexdigest()


def payfast_verify_itn(data: dict[str, str], passphrase: str = "") -> bool:
    """Verify ITN signature (SAQ A — server-to-server only)."""
    received = (data.get("signature") or "").lower()
    if not received:
        return False
    check = {k: v for k, v in data.items() if k != "signature"}
    expected = payfast_signature(check, passphrase=passphrase)
    return hmac.compare_digest(expected.lower(), received)


class PayfastProvider:
    """
    Payfast hosted checkout (sandbox or live).

    Requires PAYFAST_MERCHANT_ID, PAYFAST_MERCHANT_KEY.
    Optional PAYFAST_PASSPHRASE, PAYFAST_SANDBOX=true.
    ITN hits POST /api/v1/payments/webhooks/payfast/
    """

    name = "payfast"

    def __init__(self):
        self.merchant_id = getattr(settings, "PAYFAST_MERCHANT_ID", "") or ""
        self.merchant_key = getattr(settings, "PAYFAST_MERCHANT_KEY", "") or ""
        self.passphrase = getattr(settings, "PAYFAST_PASSPHRASE", "") or ""
        self.sandbox = getattr(settings, "PAYFAST_SANDBOX", True)

    @property
    def process_url(self) -> str:
        if self.sandbox:
            return "https://sandbox.payfast.co.za/eng/process"
        return "https://www.payfast.co.za/eng/process"

    def create_checkout(
        self,
        *,
        order_reference: str,
        amount: Decimal,
        currency: str,
        return_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> CheckoutSession:
        if not self.merchant_id or not self.merchant_key:
            logger.warning("Payfast credentials missing; falling back to sandbox provider")
            return SandboxProvider().create_checkout(
                order_reference=order_reference,
                amount=amount,
                currency=currency,
                return_url=return_url,
                cancel_url=cancel_url,
                idempotency_key=idempotency_key,
            )

        base = getattr(settings, "PUBLIC_API_BASE", "http://127.0.0.1:8000").rstrip("/")
        notify_url = f"{base}/api/v1/payments/webhooks/payfast/"
        # m_payment_id is our order reference (merchant payment id)
        fields: dict[str, str] = {
            "merchant_id": self.merchant_id,
            "merchant_key": self.merchant_key,
            "return_url": return_url or f"{base}/",
            "cancel_url": cancel_url or f"{base}/",
            "notify_url": notify_url,
            "m_payment_id": order_reference,
            "amount": f"{amount:.2f}",
            "item_name": f"Order {order_reference}",
            "custom_str1": idempotency_key[:255],
        }
        fields["signature"] = payfast_signature(fields, passphrase=self.passphrase)

        # GET redirect is not ideal for form POST; we host a thin auto-post page
        # and keep provider_reference as order ref for ITN matching.
        auto_post = f"{base}/api/v1/payments/payfast/redirect/?order={order_reference}"
        return CheckoutSession(
            provider=self.name,
            provider_reference=order_reference,  # ITN m_payment_id
            redirect_url=auto_post,
            amount=amount,
            currency=currency or "ZAR",
            form_fields=fields,
            form_action=self.process_url,
        )

    def verify_webhook(self, payload: bytes, signature: str | None = None) -> bool:
        # Payfast signs the form body; signature is inside the payload
        try:
            from urllib.parse import parse_qs

            raw = parse_qs(payload.decode("utf-8"), keep_blank_values=True)
            data = {k: (v[0] if v else "") for k, v in raw.items()}
        except Exception:
            return False
        return payfast_verify_itn(data, passphrase=self.passphrase)

    def parse_itn(self, payload: bytes) -> dict[str, Any]:
        from urllib.parse import parse_qs

        raw = parse_qs(payload.decode("utf-8"), keep_blank_values=True)
        return {k: (v[0] if v else "") for k, v in raw.items()}


def get_card_provider() -> PaymentProvider:
    """Configured card/EFT provider for hosted checkout."""
    name = (getattr(settings, "PAYMENT_PROVIDER", None) or "sandbox").lower()
    if name == "payfast":
        return PayfastProvider()
    return SandboxProvider()


def get_provider(method: str) -> PaymentProvider:
    if method == "cod":
        return CODProvider()
    # card / eft
    return get_card_provider()
