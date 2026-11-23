from django.contrib import admin

from .models import DrawerMovement, DrawerSession, Store, StoreCatalogItem, StoreStock


class StoreStockInline(admin.TabularInline):
    model = StoreStock
    extra = 0


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "sells_online", "is_active")
    inlines = [StoreStockInline]


@admin.register(StoreCatalogItem)
class StoreCatalogItemAdmin(admin.ModelAdmin):
    list_display = ("store", "variant", "bundle", "price_override")


class DrawerMovementInline(admin.TabularInline):
    model = DrawerMovement
    extra = 0


@admin.register(DrawerSession)
class DrawerSessionAdmin(admin.ModelAdmin):
    list_display = ("store", "status", "opening_float", "expected", "opened_at")
    inlines = [DrawerMovementInline]
