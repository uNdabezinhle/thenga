from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DeviceViewSet, PreferenceView

router = DefaultRouter()
router.register("devices", DeviceViewSet, basename="device")

urlpatterns = [
    path("preferences/", PreferenceView.as_view(), name="notification-preferences"),
    path("", include(router.urls)),
]
