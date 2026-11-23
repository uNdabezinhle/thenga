from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .inbox import mark_read, record_marketing_notice
from .models import DeviceRegistration, InAppNotification, NotificationPreference
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
        before = prefs.email_marketing or prefs.push_marketing
        ser.save(email_transactional=True)
        prefs.refresh_from_db()
        if not before and (prefs.email_marketing or prefs.push_marketing):
            record_marketing_notice(
                request.user,
                "Promotions are on",
                "Shared codes and your vouchers will show up here.",
            )
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


class InboxView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = InAppNotification.objects.filter(user=request.user)
        unread = qs.filter(read_at__isnull=True).count()
        rows = [
            {
                "id": note.id,
                "title": note.title,
                "body": note.body,
                "kind": note.kind,
                "read": note.read_at is not None,
                "created_at": note.created_at,
            }
            for note in qs[:50]
        ]
        return Response({"unread_count": unread, "results": rows})


class InboxReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            note = InAppNotification.objects.get(pk=pk, user=request.user)
        except InAppNotification.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "not_found",
                        "message": "Notification not found.",
                        "request_id": getattr(request, "request_id", "-"),
                    }
                },
                status=404,
            )
        mark_read(note)
        return Response({"id": note.id, "read": True})
