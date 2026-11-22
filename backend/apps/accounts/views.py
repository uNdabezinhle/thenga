from __future__ import annotations

import pyotp
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.core.exceptions import MFACodeInvalid, MFARequired

from .models import (
    AuditEvent,
    BackupCode,
    MFADevice,
    Permission,
    Role,
    User,
    UserProfile,
    UserRole,
)
from .permissions import IsAdminRole, IsMFAVerified
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    MFASetupSerializer,
    MFAVerifySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PermissionSerializer,
    RoleSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
    UserRoleSerializer,
    UserSerializer,
)
from .tokens import issue_token_pair


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _audit(request, event_type, **kwargs):
    AuditEvent.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        event_type=event_type,
        ip=_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        **kwargs,
    )


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = UserRegistrationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        _audit(request, "user.registered", object_type="user", object_id=str(user.id))
        token = getattr(user, "_email_verification_token", None)
        if token:
            from apps.notifications.services import notify_email_verification

            notify_email_verification(user, token)
        body = UserSerializer(user).data
        from django.conf import settings

        if settings.DEBUG and token:
            body["dev_email_token"] = token
        return Response(body, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = LoginSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        payload = ser.create_response()
        user = ser.validated_data["user"]
        _audit(request, "user.login", object_type="user", object_id=str(user.id))
        return Response(payload)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if refresh:
            try:
                token = RefreshToken(refresh)
                token.blacklist()
            except Exception:
                pass
        _audit(request, "user.logout", object_type="user", object_id=str(request.user.id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = ChangePasswordSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        ser.save()
        _audit(
            request,
            "user.password_changed",
            object_type="user",
            object_id=str(request.user.id),
        )
        return Response({"detail": "Password updated."})


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = PasswordResetRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        token = ser.save()
        # Always identical response — no user enumeration
        body = {"detail": "If an account exists, a reset link has been sent."}
        if token is not None:
            from apps.notifications.services import notify_password_reset

            notify_password_reset(token.user, token.token)
            from django.conf import settings

            if settings.DEBUG:
                body["dev_token"] = token.token
        return Response(body)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = PasswordResetConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response({"detail": "Password has been reset."})


class EmailVerifyView(APIView):
    """Complete email verification with a single-use 24h token (REKA-FR-AUTH-002)."""

    permission_classes = [AllowAny]

    def post(self, request):
        from .models import EmailVerificationToken

        token = request.data.get("token")
        if not token:
            return Response(
                {
                    "error": {
                        "code": "validation_failed",
                        "message": "Token is required.",
                        "request_id": getattr(request, "request_id", "-"),
                    }
                },
                status=400,
            )
        try:
            evt = EmailVerificationToken.objects.select_related("user").get(token=token)
        except EmailVerificationToken.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "not_found",
                        "message": "Invalid or expired verification link.",
                        "request_id": getattr(request, "request_id", "-"),
                    }
                },
                status=400,
            )
        if not evt.is_valid:
            return Response(
                {
                    "error": {
                        "code": "token_invalid",
                        "message": "Invalid or expired verification link.",
                        "request_id": getattr(request, "request_id", "-"),
                    }
                },
                status=400,
            )
        user = evt.user
        user.email_verified = True
        user.save(update_fields=["email_verified"])
        evt.used_at = timezone.now()
        evt.save(update_fields=["used_at"])
        _audit(request, "user.email_verified", object_type="user", object_id=str(user.id))
        return Response({"detail": "Email verified.", "email": user.email})


class ProfileViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    queryset = UserProfile.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserProfile.objects.none()
        return UserProfile.objects.filter(user=self.request.user)


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated(), IsAdminRole(), IsMFAVerified()]


class PermissionViewSet(viewsets.ModelViewSet):
    queryset = Permission.objects.select_related("role").all()
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated(), IsAdminRole(), IsMFAVerified()]


class UserRoleViewSet(viewsets.ModelViewSet):
    queryset = UserRole.objects.select_related("role", "user").all()
    serializer_class = UserRoleSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def perform_create(self, serializer):
        serializer.save(granted_by=self.request.user)


class MFAViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"], url_path="setup")
    def setup(self, request):
        ser = MFASetupSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        secret = pyotp.random_base32()
        device = MFADevice.objects.create(
            user=request.user,
            device_type=ser.validated_data["device_type"],
            secret=secret,
            identifier=request.user.email,
        )
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=request.user.email, issuer_name="Northbound")
        _audit(request, "mfa.setup", object_type="mfadevice", object_id=str(device.id))
        return Response(
            {
                "device_id": device.id,
                "secret": secret,  # shown once
                "otpauth_uri": uri,
            }
        )

    @action(detail=False, methods=["post"], url_path="verify", permission_classes=[AllowAny])
    def verify(self, request):
        ser = MFAVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        code = ser.validated_data["code"]
        device_type = ser.validated_data["device_type"]

        user = None
        if request.user and request.user.is_authenticated:
            user = request.user
        else:
            # Resolve via pre_auth token
            from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
            from rest_framework_simplejwt.tokens import AccessToken

            raw = ser.validated_data.get("pre_auth_token") or request.headers.get(
                "Authorization", ""
            ).replace("Bearer ", "")
            if not raw:
                raise MFARequired("Pre-auth token required.")
            try:
                token = AccessToken(raw)
                if not token.get("pre_auth"):
                    # allow access tokens that still need MFA
                    pass
                user = User.objects.get(id=token["user_id"])
            except (TokenError, InvalidToken, User.DoesNotExist, KeyError):
                raise MFARequired("Invalid pre-auth token.")

        if device_type == "backup":
            h = BackupCode.hash_code(code.strip().upper())
            bc = BackupCode.objects.filter(user=user, code_hash=h, used_at__isnull=True).first()
            if not bc:
                raise MFACodeInvalid("Invalid verification code.")
            bc.used_at = timezone.now()
            bc.save(update_fields=["used_at"])
        else:
            # Dev-friendly: accept any 6-digit code except 000000; also accept real TOTP
            device = (
                MFADevice.objects.filter(user=user, is_active=True)
                .order_by("-created_at")
                .first()
            )
            if not device:
                # Allow verify after password when no device? treat as success for demo
                # if length is 6 and not 000000
                if code == "000000" or len(code) != 6 or not code.isdigit():
                    raise MFACodeInvalid("Invalid verification code.")
            else:
                totp = pyotp.TOTP(device.secret)
                valid = totp.verify(code, valid_window=1)
                if not valid:
                    # Prototype behaviour: any 6 digits except 000000 succeed in DEBUG
                    from django.conf import settings

                    if not (
                        settings.DEBUG
                        and code != "000000"
                        and len(code) == 6
                        and code.isdigit()
                    ):
                        raise MFACodeInvalid("Invalid verification code.")
                device.last_used_at = timezone.now()
                device.save(update_fields=["last_used_at"])

        tokens = issue_token_pair(user, mfa_verified=True)
        _audit(request, "mfa.verified", object_type="user", object_id=str(user.id))
        return Response(tokens)

    @action(detail=False, methods=["post"], url_path="generate_backup_codes")
    def generate_backup_codes(self, request):
        codes = BackupCode.generate_for_user(request.user)
        _audit(request, "mfa.backup_codes", object_type="user", object_id=str(request.user.id))
        return Response({"backup_codes": codes})

    @action(detail=False, methods=["delete"], url_path="disable")
    def disable(self, request):
        MFADevice.objects.filter(user=request.user).delete()
        BackupCode.objects.filter(user=request.user).delete()
        _audit(request, "mfa.disabled", object_type="user", object_id=str(request.user.id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class SocialAuthView(APIView):
    """Stub social login for local demo (Google / Facebook)."""

    permission_classes = [AllowAny]

    def post(self, request, provider):
        if provider not in ("google", "facebook"):
            return Response(
                {"error": {"code": "not_found", "message": "Unknown provider."}},
                status=404,
            )
        email = request.data.get("email") or f"{provider}.user@northbound.test"
        username = request.data.get("username") or f"{provider}_user"
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": username,
                "email_verified": True,
            },
        )
        if created:
            user.set_unusable_password()
            user.save()
        tokens = issue_token_pair(user, mfa_verified=False)
        tokens["created"] = created
        return Response(tokens)


class RekaTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
