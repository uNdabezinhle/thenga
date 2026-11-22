from rest_framework import serializers

from .models import DeviceRegistration, NotificationPreference


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = (
            "email_transactional",
            "email_marketing",
            "push_order_updates",
            "push_marketing",
            "updated_at",
        )
        read_only_fields = ("email_transactional", "updated_at")


class DeviceRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceRegistration
        fields = ("id", "token", "platform", "is_active", "created_at", "last_seen_at")
        read_only_fields = ("id", "created_at", "last_seen_at")
