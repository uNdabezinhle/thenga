from django.urls import path

from .views import AdListView, StaffAdDetailView, StaffAdListView

urlpatterns = [
    path("staff/", StaffAdListView.as_view(), name="staff-ad-list"),
    path("staff/<int:pk>/", StaffAdDetailView.as_view(), name="staff-ad-detail"),
    path("", AdListView.as_view(), name="ad-list"),
]
