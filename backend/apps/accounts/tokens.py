"""JWT helpers — pre-auth vs full tokens (REKA-FR-AUTH-005, ADR-0004)."""
from __future__ import annotations

from datetime import timedelta

from rest_framework_simplejwt.tokens import AccessToken, RefreshToken


def issue_token_pair(user, *, mfa_verified: bool = False) -> dict:
    refresh = RefreshToken.for_user(user)
    refresh["mfa_verified"] = mfa_verified
    access = refresh.access_token
    access["mfa_verified"] = mfa_verified
    access["pre_auth"] = False
    return {
        "access": str(access),
        "refresh": str(refresh),
        "mfa_verified": mfa_verified,
    }


def issue_pre_auth_token(user) -> dict:
    """5-minute access token that only unlocks MFA verification.

    Token type remains ``access`` so simplejwt accepts it; the ``pre_auth``
    claim is enforced in ``RekaJWTAuthentication``.
    """
    token = AccessToken()
    token.set_exp(lifetime=timedelta(minutes=5))
    token["user_id"] = user.id
    token["mfa_verified"] = False
    token["pre_auth"] = True
    return {
        "pre_auth_token": str(token),
        "mfa_required": True,
        "mfa_verified": False,
    }
