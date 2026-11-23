from django.contrib import admin

from .models import (
    Address,
    Order,
    OrderEvent,
    OrderItem,
    Payment,
    Refund,
    Shipment,
    ShipmentEvent,
    ShippingRate,
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "product_name_snapshot",
        "sku_snapshot",
        "unit_price",
        "quantity",
        "line_total",
    )


class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    readonly_fields = ("from_status", "to_status", "note", "created_at")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "status", "grand_total", "placed_at")
    list_filter = ("status",)
    search_fields = ("reference", "user__email")
    inlines = [OrderItemInline, OrderEventInline]


admin.site.register(Address)
admin.site.register(Payment)
admin.site.register(Refund)
admin.site.register(Shipment)
admin.site.register(ShipmentEvent)


@admin.register(ShippingRate)
class ShippingRateAdmin(admin.ModelAdmin):
    list_display = ("method_name", "price", "estimated_days", "sort_order")
