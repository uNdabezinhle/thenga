from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import staff_views
from .views import AddressViewSet, OrderViewSet

router = DefaultRouter()
router.register("addresses", AddressViewSet, basename="address")
router.register("", OrderViewSet, basename="order")

urlpatterns = [
    path("staff/shipping-rates/", staff_views.staff_shipping_rates, name="staff-shipping-rates"),
    path(
        "staff/shipping-rates/<int:pk>/",
        staff_views.staff_shipping_rate_update,
        name="staff-shipping-rate",
    ),
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
    path(
        "staff/<str:reference>/dispatch/",
        staff_views.staff_dispatch,
        name="staff-order-dispatch",
    ),
    path(
        "staff/<str:reference>/courier/",
        staff_views.staff_courier,
        name="staff-order-courier",
    ),
    path("", include(router.urls)),
]
