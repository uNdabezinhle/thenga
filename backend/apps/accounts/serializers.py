from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from .models import (
    BackupCode,
    EmailVerificationToken,
    MFADevice,
    PasswordResetToken,
    Permission,
    Role,
    User,
    UserProfile,
    UserRole,
)
from .tokens import issue_pre_auth_token, issue_token_pair


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("id", "email", "username", "password", "password2", "phone_number")
        read_only_fields = ("id",)

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."}
            )
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        token = EmailVerificationToken.create_for(user)
        # Attach for DEBUG responses / tests (never log the token in production)
        user._email_verification_token = token.token
        return user


class UserSerializer(serializers.ModelSerializer):
    is_staff_ops = serializers.SerializerMethodField()
    mfa_enabled = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "phone_number",
            "email_verified",
            "date_joined",
            "is_staff",
            "is_staff_ops",
            "mfa_enabled",
        )
        read_only_fields = fields

    def get_mfa_enabled(self, obj):
        return obj.mfa_devices.filter(is_active=True).exists()

    def get_is_staff_ops(self, obj):
        if obj.is_superuser or obj.is_staff:
            return True
        from .models import UserRole

        return UserRole.objects.filter(
            user=obj,
            role__name__in=("Staff", "Administrator"),
            role__is_active=True,
        ).exists()


class UserProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = UserProfile
        fields = (
            "id",
            "email",
            "username",
            "display_name",
            "first_name",
            "last_name",
            "address",
            "date_of_birth",
            "preferences",
        )
        read_only_fields = ("id", "email", "username", "display_name")


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        password = attrs["password"]
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"error": "Invalid credentials."},
                code="authentication_failed",
            )

        if user.is_locked:
            raise serializers.ValidationError(
                {"error": "Account temporarily locked. Try again later."}
            )

        user_auth = authenticate(
            request=self.context.get("request"),
            email=user.email,
            password=password,
        )
        # AbstractBaseUser authenticate via custom backend may fail; fall back
        if user_auth is None:
            if user.check_password(password) and user.is_active:
                user_auth = user
            else:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= 5:
                    user.locked_until = timezone.now() + timezone.timedelta(minutes=15)
                user.save(update_fields=["failed_login_attempts", "locked_until"])
                raise serializers.ValidationError(
                    {"error": "Invalid credentials."},
                    code="authentication_failed",
                )

        user.failed_login_attempts = 0
        user.locked_until = None
        user.save(update_fields=["failed_login_attempts", "locked_until"])
        attrs["user"] = user
        return attrs

    def create_response(self):
        user = self.validated_data["user"]
        has_mfa = MFADevice.objects.filter(user=user, is_active=True).exists()
        if has_mfa:
            return issue_pre_auth_token(user)
        return issue_token_pair(user, mfa_verified=False)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError(
                {"current_password": "Current password is incorrect."}
            )
        validate_password(attrs["new_password"], user)
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self):
        email = self.validated_data["email"]
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None  # no enumeration
        return PasswordResetToken.create_for(user)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        try:
            prt = PasswordResetToken.objects.select_related("user").get(
                token=attrs["token"]
            )
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError({"token": "Invalid or expired token."})
        if not prt.is_valid:
            raise serializers.ValidationError({"token": "Invalid or expired token."})
        validate_password(attrs["new_password"], prt.user)
        attrs["prt"] = prt
        return attrs

    def save(self):
        prt = self.validated_data["prt"]
        user = prt.user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        prt.used_at = timezone.now()
        prt.save(update_fields=["used_at"])
        return user


class MFASetupSerializer(serializers.Serializer):
    device_type = serializers.ChoiceField(
        choices=MFADevice.DeviceType.choices, default=MFADevice.DeviceType.AUTHENTICATOR
    )


class MFAVerifySerializer(serializers.Serializer):
    code = serializers.CharField()
    device_type = serializers.ChoiceField(
        choices=["authenticator", "sms", "email", "backup"],
        default="authenticator",
    )
    pre_auth_token = serializers.CharField(required=False, allow_blank=True)


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ("id", "name", "description", "is_active", "created_at")
        read_only_fields = ("id", "created_at")


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = (
            "id",
            "role",
            "module",
            "can_create",
            "can_read",
            "can_update",
            "can_delete",
        )


class UserRoleSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = UserRole
        fields = ("id", "user", "role", "role_name", "granted_by", "granted_at")
        read_only_fields = ("id", "granted_by", "granted_at", "role_name")
