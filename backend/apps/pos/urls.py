from django.urls import path

from .views import pos_catalog, pos_drawer, pos_sale, pos_scan, pos_stores, pos_sync

urlpatterns = [
    path("stores/", pos_stores, name="pos-stores"),
    path("catalog/", pos_catalog, name="pos-catalog"),
    path("scan/", pos_scan, name="pos-scan"),
    path("sales/", pos_sale, name="pos-sale"),
    path("sales/sync/", pos_sync, name="pos-sync"),
    path("drawer/", pos_drawer, name="pos-drawer"),
]
