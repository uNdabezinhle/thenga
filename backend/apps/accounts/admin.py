from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

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


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "username", "email_verified", "is_staff", "is_active")
    search_fields = ("email", "username")
    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Flags", {"fields": ("email_verified", "is_active", "is_staff", "is_superuser")}),
        ("Contact", {"fields": ("phone_number",)}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "password1", "password2"),
            },
        ),
    )


admin.site.register(UserProfile)
admin.site.register(Role)
admin.site.register(Permission)
admin.site.register(UserRole)
admin.site.register(MFADevice)
admin.site.register(BackupCode)
admin.site.register(AuditEvent)
