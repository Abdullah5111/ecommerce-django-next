from django.contrib import admin
from .models import Category, Product, ProductImage, Review, ReviewImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "full_slug", "level", "parent")
    list_filter = ("parent",)
    prepopulated_fields = {"slug": ("name",)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name", "category", "price", "compare_at_price",
        "rating_avg", "rating_count", "stock", "is_active",
    )
    list_filter = ("category", "is_active")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline]


class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 0


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "product", "user", "rating", "title",
        "verified_purchase", "helpful_count", "created_at",
    )
    list_filter = ("rating", "verified_purchase")
    search_fields = ("product__name", "user__username", "title", "body")
    readonly_fields = ("helpful_count",)
    inlines = [ReviewImageInline]
