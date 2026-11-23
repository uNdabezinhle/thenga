from django.urls import path

from .views import onboard, onboard_status, package_list

urlpatterns = [
    path("packages/", package_list, name="platform-packages"),
    path("onboarding/", onboard, name="platform-onboarding"),
    path("onboarding/status/", onboard_status, name="platform-onboarding-status"),
]
