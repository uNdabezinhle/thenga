"""Request ID and cart session middleware (ADR-0005)."""
from __future__ import annotations

import hashlib
import hmac
import uuid

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class RequestIDMiddleware(MiddlewareMixin):
    """Attach / echo X-Request-ID and store on the request for logging."""

    header = "HTTP_X_REQUEST_ID"

    def process_request(self, request):
        rid = request.META.get(self.header) or str(uuid.uuid4())
        request.request_id = rid
        return None

    def process_response(self, request, response):
        rid = getattr(request, "request_id", None) or str(uuid.uuid4())
        response["X-Request-ID"] = rid
        return response


def sign_cart_session(session_id: str) -> str:
    """HMAC-SHA256 of the session id for integrity checks."""
    secret = settings.CART_SESSION_HMAC_SECRET.encode("utf-8")
    return hmac.new(secret, session_id.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_cart_session(session_id: str, signature: str | None = None) -> bool:
    """Validate UUID shape; optional signature for signed clients."""
    try:
        uuid.UUID(str(session_id))
    except (ValueError, TypeError, AttributeError):
        return False
    if signature:
        expected = sign_cart_session(session_id)
        return hmac.compare_digest(expected, signature)
    return True


class CartSessionMiddleware(MiddlewareMixin):
    """Read X-Cart-Session and set request.cart_session_id (ADR-0005)."""

    header = "HTTP_X_CART_SESSION"
    sig_header = "HTTP_X_CART_SESSION_SIG"

    def process_request(self, request):
        raw = request.META.get(self.header)
        if not raw:
            request.cart_session_id = None
            request.cart_session_valid = False
            return None
        sig = request.META.get(self.sig_header)
        if verify_cart_session(raw, sig):
            request.cart_session_id = str(raw).strip()
            request.cart_session_valid = True
        else:
            request.cart_session_id = None
            request.cart_session_valid = False
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Baseline browser security headers (REKA-NFR-SEC-005 companion)."""

    def process_response(self, request, response):
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("X-Frame-Options", "DENY")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        # HSTS only when HTTPS terminated (or SECURE_SSL_REDIRECT)
        if not settings.DEBUG and getattr(settings, "SECURE_SSL_REDIRECT", False):
            response.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        # Avoid caching authenticated/PII responses by default
        path = request.path or ""
        if path.startswith("/api/") and "Cache-Control" not in response:
            if any(
                p in path
                for p in (
                    "/auth/",
                    "/cart/",
                    "/orders/",
                    "/payments/",
                    "/notifications/",
                )
            ):
                response["Cache-Control"] = "no-store"
        return response
