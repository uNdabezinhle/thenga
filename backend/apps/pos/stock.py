"""Pick the warehouse a sale reserves. Online and Harbour share Inventory."""
from __future__ import annotations

from apps.catalogue.models import Inventory


def sells_from_website(order) -> bool:
    store_id = getattr(order, "store_id", None)
    if not store_id:
        return True
    store = getattr(order, "store", None)
    if store is None or store.pk != store_id:
        from apps.pos.models import Store

        store = Store.objects.get(pk=store_id)
    return bool(store.sells_online)


def locked_stock(order, variant_id):
    if sells_from_website(order):
        return Inventory.objects.select_for_update().get(variant_id=variant_id)
    from apps.pos.models import StoreStock

    return StoreStock.objects.select_for_update().get(
        store_id=order.store_id, variant_id=variant_id
    )
