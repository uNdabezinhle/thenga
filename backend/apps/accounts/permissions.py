"""Permission primitives — Access Control Matrix §4."""
from __future__ import annotations

from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import Module, Permission, UserRole


class IsAuthenticatedCustomer(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsMFAVerified(BasePermission):
    message = "MFA verification required."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        claims = getattr(request.user, "_token_claims", {})
        return bool(claims.get("mfa_verified"))


class IsObjectOwner(BasePermission):
    owner_field = "user"

    def has_object_permission(self, request, view, obj):
        field = getattr(view, "owner_field", self.owner_field)
        owner = obj
        for part in field.split("."):
            owner = getattr(owner, part, None)
            if owner is None:
                break
        return owner == request.user


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return UserRole.objects.filter(
            user=request.user, role__name="Administrator", role__is_active=True
        ).exists()


class IsStaffRole(BasePermission):
    """Staff or Administrator (order ops, refunds, support)."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser or request.user.is_staff:
            return True
        return UserRole.objects.filter(
            user=request.user,
            role__name__in=("Staff", "Administrator"),
            role__is_active=True,
        ).exists()


class HasModulePermission(BasePermission):
    """Match Role→Permission.module against view.required_module + HTTP method."""

    method_map = {
        "GET": "can_read",
        "HEAD": "can_read",
        "OPTIONS": "can_read",
        "POST": "can_create",
        "PUT": "can_update",
        "PATCH": "can_update",
        "DELETE": "can_delete",
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        module = getattr(view, "required_module", None)
        if module is None:
            return False
        flag = self.method_map.get(request.method, "can_read")
        role_ids = UserRole.objects.filter(user=request.user).values_list("role_id", flat=True)
        return Permission.objects.filter(
            role_id__in=role_ids,
            role__is_active=True,
            module=module,
            **{flag: True},
        ).exists()
