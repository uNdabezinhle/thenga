from django.contrib import admin

from .models import DeviceRegistration, InAppNotification, NotificationLog, NotificationPreference

admin.site.register(NotificationPreference)
admin.site.register(DeviceRegistration)
admin.site.register(InAppNotification)


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("template", "channel", "recipient", "status", "created_at")
    list_filter = ("status", "channel", "template")
    readonly_fields = (
        "user",
        "channel",
        "template",
        "recipient",
        "subject",
        "status",
        "error",
        "metadata",
        "created_at",
    )
