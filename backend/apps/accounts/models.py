"""Identity & access models — Data Model §2, ADR-0010."""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class Module(models.TextChoices):
    AUTH = "auth", "Authentication"
    CATALOGUE = "catalogue", "Catalogue"
    CART = "cart", "Cart"
    ORDERS = "orders", "Orders"
    PAYMENTS = "payments", "Payments"
    SHIPPING = "shipping", "Shipping"
    PROMOTIONS = "promotions", "Promotions"
    ADMIN = "admin", "Administration"


class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        if not username:
            raise ValueError("Username is required")
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("email_verified", True)
        return self.create_user(email, username, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    phone_number = models.CharField(max_length=32, blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(blank=True, null=True)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        indexes = [
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return self.email

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    preferences = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Profile<{self.user_id}>"

    @property
    def display_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.user.username


class Role(models.Model):
    name = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Permission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permissions")
    module = models.CharField(max_length=32, choices=Module.choices)
    can_create = models.BooleanField(default=False)
    can_read = models.BooleanField(default=False)
    can_update = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)

    class Meta:
        unique_together = ("role", "module")

    def __str__(self):
        return f"{self.role.name}:{self.module}"


class UserRole(models.Model):
    """Blocking gap fix — USER ↔ ROLE link (ADR-0010, Data Model §2)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_roles")
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="roles_granted",
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "role")

    def __str__(self):
        return f"{self.user_id}→{self.role.name}"


class MFADevice(models.Model):
    class DeviceType(models.TextChoices):
        AUTHENTICATOR = "authenticator", "Authenticator"
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mfa_devices")
    device_type = models.CharField(max_length=20, choices=DeviceType.choices)
    identifier = models.CharField(max_length=255, blank=True)
    secret = models.CharField(max_length=255)  # TOTP secret; encrypt at rest in prod
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"MFA<{self.user_id}:{self.device_type}>"


class BackupCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="backup_codes")
    code_hash = models.CharField(max_length=128)
    used_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def hash_code(code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    @classmethod
    def generate_for_user(cls, user, count: int = 8) -> list[str]:
        cls.objects.filter(user=user, used_at__isnull=True).delete()
        plain = []
        for _ in range(count):
            part_a = secrets.token_hex(2).upper()
            part_b = secrets.token_hex(2).upper()
            code = f"{part_a}-{part_b}"
            plain.append(code)
            cls.objects.create(user=user, code_hash=cls.hash_code(code))
        return plain


class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_tokens")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(blank=True, null=True)

    @classmethod
    def create_for(cls, user) -> "EmailVerificationToken":
        return cls.objects.create(user=user, token=secrets.token_urlsafe(32))

    @property
    def is_valid(self) -> bool:
        if self.used_at:
            return False
        return self.created_at >= timezone.now() - timedelta(hours=24)


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_resets")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(blank=True, null=True)

    @classmethod
    def create_for(cls, user) -> "PasswordResetToken":
        return cls.objects.create(user=user, token=secrets.token_urlsafe(32))

    @property
    def is_valid(self) -> bool:
        if self.used_at:
            return False
        return self.created_at >= timezone.now() - timedelta(hours=1)


class SocialAccount(models.Model):
    class Provider(models.TextChoices):
        GOOGLE = "google", "Google"
        FACEBOOK = "facebook", "Facebook"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="social_accounts")
    provider = models.CharField(max_length=32, choices=Provider.choices)
    provider_id = models.CharField(max_length=255)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_expires = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ("provider", "provider_id")


class AuditEvent(models.Model):
    """Append-only audit log — Access Control Matrix §10."""

    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_events"
    )
    event_type = models.CharField(max_length=64)
    object_type = models.CharField(max_length=64, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["object_type", "object_id"]),
        ]
