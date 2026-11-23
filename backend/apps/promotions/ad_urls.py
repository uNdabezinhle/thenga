from django.urls import path

from .views import AdClickView, AdListView, StaffAdDetailView, StaffAdListView

urlpatterns = [
    path("staff/", StaffAdListView.as_view(), name="staff-ad-list"),
    path("staff/<int:pk>/", StaffAdDetailView.as_view(), name="staff-ad-detail"),
    path("<int:pk>/click/", AdClickView.as_view(), name="ad-click"),
    path("", AdListView.as_view(), name="ad-list"),
]
