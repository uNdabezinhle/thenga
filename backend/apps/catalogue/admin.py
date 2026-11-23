from django.contrib import admin

from .models import FlashPrice
from .models import (
    Brand,
    Category,
    Inventory,
    Product,
    ProductAttribute,
    ProductImage,
    ProductVariant,
    Review,
)


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


class AttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "brand", "category", "base_price", "is_active")
    list_filter = ("is_active", "category", "brand")
    search_fields = ("sku", "name")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [VariantInline, AttributeInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("sku", "product", "label", "is_active")


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("variant", "quantity", "reserved_quantity", "warehouse")


@admin.register(FlashPrice)
class FlashPriceAdmin(admin.ModelAdmin):
    list_display = ("product", "sale_price", "starts_at", "ends_at", "is_active")
    list_filter = ("is_active",)


admin.site.register(Category)
admin.site.register(Brand)
admin.site.register(ProductImage)
admin.site.register(Review)
