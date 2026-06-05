from rest_framework import serializers
from .models import Category, Product, ProductImage


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "full_slug", "level", "parent")


class CategoryTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "full_slug", "level", "children")

    def get_children(self, obj):
        return CategoryTreeSerializer(obj.children.all(), many=True).data


def _minimal_cat(cat):
    return {
        "id": cat.id,
        "name": cat.name,
        "slug": cat.slug,
        "full_slug": cat.full_slug,
    }


class CategoryDetailSerializer(serializers.ModelSerializer):
    ancestors = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "full_slug", "level", "ancestors", "children")

    def get_ancestors(self, obj):
        chain = []
        node = obj.parent
        while node is not None:
            chain.append(_minimal_cat(node))
            node = node.parent
        chain.reverse()
        return chain

    def get_children(self, obj):
        return [_minimal_cat(c) for c in obj.children.all()]


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("id", "url", "alt", "sort_order")


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source="category", write_only=True
    )
    images = ProductImageSerializer(many=True, read_only=True)
    is_on_sale = serializers.BooleanField(read_only=True)
    discount_percent = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id", "name", "slug", "description", "price", "compare_at_price",
            "rating_avg", "rating_count", "stock",
            "image_url", "images", "is_on_sale", "discount_percent",
            "is_active", "is_featured", "category", "category_id",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "slug", "created_at", "updated_at",
            "rating_avg", "rating_count",
        )
