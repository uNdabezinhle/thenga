from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import staff_views
from .views import AddressViewSet, OrderViewSet

router = DefaultRouter()
router.register("addresses", AddressViewSet, basename="address")
router.register("", OrderViewSet, basename="order")

urlpatterns = [
    path("staff/", staff_views.staff_order_list, name="staff-order-list"),
    path(
        "staff/<str:reference>/",
        staff_views.staff_order_detail,
        name="staff-order-detail",
    ),
    path(
        "staff/<str:reference>/advance/",
        staff_views.staff_advance,
        name="staff-order-advance",
    ),
    path("", include(router.urls)),
]
