from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DeviceRegistration, NotificationPreference
from .serializers import DeviceRegistrationSerializer, NotificationPreferenceSerializer
from .services import get_or_create_prefs


class PreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        prefs = get_or_create_prefs(request.user)
        return Response(NotificationPreferenceSerializer(prefs).data)

    def patch(self, request):
        prefs = get_or_create_prefs(request.user)
        ser = NotificationPreferenceSerializer(prefs, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        # email_transactional cannot be turned off — force true
        ser.save(email_transactional=True)
        return Response(ser.data)


class DeviceViewSet(viewsets.ModelViewSet):
    """Register/unregister push devices (REKA-FR-NOT-002)."""

    serializer_class = DeviceRegistrationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        return DeviceRegistration.objects.filter(user=self.request.user, is_active=True)

    def perform_create(self, serializer):
        token = serializer.validated_data["token"]
        existing = DeviceRegistration.objects.filter(
            user=self.request.user, token=token
        ).first()
        if existing:
            existing.is_active = True
            existing.platform = serializer.validated_data.get(
                "platform", existing.platform
            )
            existing.save()
            serializer.instance = existing
            return
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        device = self.get_object()
        device.is_active = False
        device.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)
