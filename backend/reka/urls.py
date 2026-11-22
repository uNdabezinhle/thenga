from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.frontend import spa_asset, spa_index
from apps.core.health import live, ready

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/live/", live, name="health-live"),
    path("health/ready/", ready, name="health-ready"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/v1/app/", include("apps.core.urls")),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/products/", include("apps.catalogue.urls")),
    path("api/v1/cart/", include("apps.cart.urls")),
    path("api/v1/orders/", include("apps.orders.urls")),
    path("api/v1/payments/", include("apps.payments.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    # Northbound SPA (local/dev convenience — same origin as API)
    path("", spa_index, name="spa-index"),
    path("app.js", spa_asset, {"path": "app.js"}, name="spa-app-js"),
]
