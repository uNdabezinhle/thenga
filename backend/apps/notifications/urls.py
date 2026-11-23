from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DeviceViewSet, InboxReadView, InboxView, MerchantLogView, PreferenceView

router = DefaultRouter()
router.register("devices", DeviceViewSet, basename="device")

urlpatterns = [
    path("preferences/", PreferenceView.as_view(), name="notification-preferences"),
    path("log/", MerchantLogView.as_view(), name="notification-log"),
    path("inbox/", InboxView.as_view(), name="notification-inbox"),
    path("inbox/<int:pk>/read/", InboxReadView.as_view(), name="notification-inbox-read"),
    path("", include(router.urls)),
]
