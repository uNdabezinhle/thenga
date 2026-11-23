from django.contrib import admin

from .models import Cart, CartDiscount, CartItem, Coupon, SavedForLater, ShippingEstimate


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_id", "is_active", "updated_at")
    inlines = [CartItemInline]


admin.site.register(CartDiscount)
admin.site.register(ShippingEstimate)
admin.site.register(SavedForLater)


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "discount_type", "amount", "is_active", "times_used")
