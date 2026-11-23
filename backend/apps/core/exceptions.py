"""Uniform error envelope per API Design Standards §6."""
from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


class RekaAPIException(APIException):
    """Base exception with a stable machine-readable code."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "error"
    default_detail = "An error occurred."

    def __init__(self, detail=None, code=None, field=None, details=None):
        self.field = field
        self.details = details
        if code:
            self.default_code = code
        super().__init__(detail=detail, code=code or self.default_code)


class CartItemOutOfStock(RekaAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "cart_item_out_of_stock"
    default_detail = "Insufficient stock for this item."


class DiscountCodeInvalid(RekaAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "discount_code_invalid"
    default_detail = "That discount code is not valid."


class DiscountAlreadyApplied(RekaAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "discount_already_applied"
    default_detail = "This discount code is already applied."


class BundleLocked(RekaAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "bundle_locked"
    default_detail = "Change the bundle from the shop."


class CartSessionInvalid(RekaAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "cart_session_invalid"
    default_detail = "Cart session is missing or invalid."


class MFARequired(RekaAPIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_code = "mfa_required"
    default_detail = "Multi-factor authentication is required."


class MFACodeInvalid(RekaAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "mfa_code_invalid"
    default_detail = "Invalid verification code."


def _request_id(context) -> str:
    request = context.get("request")
    if request is not None:
        return getattr(request, "request_id", "-") or "-"
    return "-"


def reka_exception_handler(exc, context):
    response = exception_handler(exc, context)
    rid = _request_id(context)

    if response is None:
        return None

    code = getattr(exc, "default_code", None) or getattr(exc, "code", None) or "error"
    if isinstance(code, str) is False:
        code = "error"

    field = getattr(exc, "field", None)
    details = getattr(exc, "details", None)
    message = None

    data = response.data

    if isinstance(exc, ValidationError):
        code = "validation_failed"
        message = "Check the highlighted fields."
        errors = []
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "non_field_errors":
                    fname = None
                else:
                    fname = key
                msgs = value if isinstance(value, list) else [value]
                for m in msgs:
                    errors.append(
                        {
                            "field": fname,
                            "code": "invalid",
                            "message": str(m),
                        }
                    )
        elif isinstance(data, list):
            for m in data:
                errors.append({"field": None, "code": "invalid", "message": str(m)})
        response.data = {
            "error": {
                "code": code,
                "message": message,
                "errors": errors,
                "request_id": rid,
            }
        }
        return response

    if isinstance(data, dict):
        if "detail" in data:
            message = str(data["detail"])
        elif "error" in data and isinstance(data["error"], str):
            message = data["error"]
        else:
            # flatten first message
            for key, value in data.items():
                if isinstance(value, list) and value:
                    message = str(value[0])
                    field = field or key
                    break
                if isinstance(value, str):
                    message = value
                    field = field or key
                    break

    if message is None:
        message = str(getattr(exc, "detail", "An error occurred."))

    # Prefer explicit code from RekaAPIException
    if isinstance(exc, RekaAPIException):
        code = exc.default_code
        if getattr(exc, "detail", None) is not None:
            message = str(exc.detail)

    payload = {
        "code": code if isinstance(code, str) else "error",
        "message": message,
        "request_id": rid,
    }
    if field:
        payload["field"] = field
    if details:
        payload["details"] = details

    response.data = {"error": payload}
    return response
