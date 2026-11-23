from django.urls import path

from .specials_views import (
    BundleAddView,
    BundleListView,
    LoyaltyRedeemView,
    LoyaltyView,
    ReferralView,
    StaffBundleDetailView,
    StaffBundleListView,
    StaffFlashDetailView,
    StaffFlashListView,
)
from .views import PromotionListView, StaffPromotionDetailView, StaffPromotionListView

urlpatterns = [
    path("loyalty/", LoyaltyView.as_view(), name="loyalty"),
    path("loyalty/redeem/", LoyaltyRedeemView.as_view(), name="loyalty-redeem"),
    path("referrals/", ReferralView.as_view(), name="referral"),
    path("bundles/", BundleListView.as_view(), name="bundle-list"),
    path("bundles/<int:pk>/add/", BundleAddView.as_view(), name="bundle-add"),
    path("staff/flashes/", StaffFlashListView.as_view(), name="staff-flash-list"),
    path("staff/flashes/<int:pk>/", StaffFlashDetailView.as_view(), name="staff-flash-detail"),
    path("staff/bundles/", StaffBundleListView.as_view(), name="staff-bundle-list"),
    path("staff/bundles/<int:pk>/", StaffBundleDetailView.as_view(), name="staff-bundle-detail"),
    path("staff/", StaffPromotionListView.as_view(), name="staff-promotion-list"),
    path(
        "staff/<str:code>/",
        StaffPromotionDetailView.as_view(),
        name="staff-promotion-detail",
    ),
    path("", PromotionListView.as_view(), name="promotion-list"),
]
