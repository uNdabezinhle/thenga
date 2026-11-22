from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BrandViewSet, CategoryViewSet, ProductViewSet

router = DefaultRouter()
router.register("", ProductViewSet, basename="product")
# categories & brands under products namespace helpers
router.register("meta/categories", CategoryViewSet, basename="category")
router.register("meta/brands", BrandViewSet, basename="brand")

urlpatterns = [
    path("", include(router.urls)),
]
