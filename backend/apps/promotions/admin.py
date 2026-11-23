from django.contrib import admin

from .models import ShopAd, Voucher


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ("code", "owner", "amount", "remaining_amount", "expires_at")
    search_fields = ("code", "owner__email")


@admin.register(ShopAd)
class ShopAdAdmin(admin.ModelAdmin):
    list_display = ("title", "placement", "is_active", "sort_order")
    list_filter = ("placement", "is_active")
