from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CartViewSet, SavedItemsViewSet

router = DefaultRouter()
router.register("cart", CartViewSet, basename="cart")
router.register("saved-items", SavedItemsViewSet, basename="saved-items")

urlpatterns = [
    path("", include(router.urls)),
]
