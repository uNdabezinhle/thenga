from django.urls import path

from .views import PromotionListView, StaffPromotionDetailView, StaffPromotionListView

urlpatterns = [
    path("staff/", StaffPromotionListView.as_view(), name="staff-promotion-list"),
    path(
        "staff/<str:code>/",
        StaffPromotionDetailView.as_view(),
        name="staff-promotion-detail",
    ),
    path("", PromotionListView.as_view(), name="promotion-list"),
]
