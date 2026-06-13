from django.contrib import admin

from .models import Coupon, CouponRedemption


class CouponRedemptionInline(admin.TabularInline):
    model = CouponRedemption
    extra = 0
    readonly_fields = ("user", "order", "discount_amount", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "kind", "value", "is_active", "starts_at", "expires_at")
    list_filter = ("kind", "is_active")
    search_fields = ("code",)
    filter_horizontal = ("categories", "products")
    inlines = [CouponRedemptionInline]


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ("coupon", "user", "order", "discount_amount", "created_at")
    readonly_fields = ("coupon", "user", "order", "discount_amount", "created_at")
