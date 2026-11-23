from django.urls import path

from .views import (
    ad_desk,
    catalogue_import,
    onboard,
    onboard_status,
    package_list,
    payfast_keys,
    staff_invite,
    store_create,
)

urlpatterns = [
    path("packages/", package_list, name="platform-packages"),
    path("onboarding/", onboard, name="platform-onboarding"),
    path("onboarding/status/", onboard_status, name="platform-onboarding-status"),
    path("staff/", staff_invite, name="platform-staff"),
    path("catalogue/", catalogue_import, name="platform-catalogue"),
    path("stores/", store_create, name="platform-stores"),
    path("payfast/", payfast_keys, name="platform-payfast"),
    path("ads/", ad_desk, name="platform-ads"),
]
