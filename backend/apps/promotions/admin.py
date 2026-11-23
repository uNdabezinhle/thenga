from django.contrib import admin

from .models import Bundle, BundleItem, LoyaltyAccount, ReferralProfile, ShopAd, Voucher


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ("code", "owner", "amount", "remaining_amount", "expires_at")
    search_fields = ("code", "owner__email")


class BundleItemInline(admin.TabularInline):
    model = BundleItem
    extra = 0


@admin.register(Bundle)
class BundleAdmin(admin.ModelAdmin):
    list_display = ("title", "price", "is_active")
    inlines = [BundleItemInline]


admin.site.register(LoyaltyAccount)
admin.site.register(ReferralProfile)


@admin.register(ShopAd)
class ShopAdAdmin(admin.ModelAdmin):
    list_display = ("title", "placement", "is_active", "sort_order")
    list_filter = ("placement", "is_active")
