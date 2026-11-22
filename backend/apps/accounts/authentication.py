from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class RekaJWTAuthentication(JWTAuthentication):
    """Attach mfa_verified / pre_auth claims onto request.auth payload."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        # Store claims for permission classes
        user._token_claims = {
            "mfa_verified": bool(validated_token.get("mfa_verified", False)),
            "pre_auth": bool(validated_token.get("pre_auth", False)),
            "token_type": validated_token.get("token_type", "access"),
        }
        return user

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, validated_token = result
        if validated_token.get("pre_auth"):
            # Pre-auth tokens may only hit MFA endpoints
            path = request.path or ""
            if "/auth/mfa/" not in path and "/api/v1/auth/mfa/" not in path:
                raise InvalidToken("Pre-auth token restricted to MFA verification")
        return user, validated_token
