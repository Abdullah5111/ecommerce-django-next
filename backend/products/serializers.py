from django.core.validators import FileExtensionValidator
from rest_framework import serializers
from .models import Category, Product, ProductImage, ProductVariant, Review, ReviewImage

MAX_REVIEW_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB per photo
# SVG excluded: a real image that can carry <script>, served from our origin.
ALLOWED_REVIEW_IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "gif")


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


class ProductVariantSerializer(serializers.ModelSerializer):
    effective_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    in_stock = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = ("id", "options", "sku", "stock", "price", "effective_price", "in_stock")

    def get_in_stock(self, obj):
        return obj.stock > 0


def _active_variants(product):
    # Uses the prefetched list; seeds each variant's product back-reference so
    # effective_price doesn't fire a query per variant.
    out = []
    for v in product.variants.all():
        if v.is_active:
            v.product = product
            out.append(v)
    return out


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source="category", write_only=True
    )
    images = ProductImageSerializer(many=True, read_only=True)
    is_on_sale = serializers.BooleanField(read_only=True)
    discount_percent = serializers.IntegerField(read_only=True)
    has_variants = serializers.SerializerMethodField()
    price_from = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id", "name", "slug", "description", "price", "compare_at_price",
            "rating_avg", "rating_count", "stock", "sold_count",
            "image_url", "images", "is_on_sale", "discount_percent",
            "has_variants", "price_from",
            "is_active", "is_featured", "specifications",
            "category", "category_id",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "slug", "created_at", "updated_at",
            "rating_avg", "rating_count", "sold_count", "specifications",
        )

    def get_has_variants(self, obj):
        return len(_active_variants(obj)) > 0

    def get_price_from(self, obj):
        # Cheapest active variant, or the product's own price when there are none.
        variants = _active_variants(obj)
        if not variants:
            return str(obj.price)
        return str(min(v.effective_price for v in variants))


class ProductDetailSerializer(ProductSerializer):
    """Product detail carries the full variant list; cards do not."""

    variants = serializers.SerializerMethodField()

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + ("variants",)

    def get_variants(self, obj):
        return ProductVariantSerializer(_active_variants(obj), many=True).data


class ReviewImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ReviewImage
        fields = ("id", "image", "sort_order")

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class ReviewImageUploadSerializer(serializers.Serializer):
    """Validates one uploaded review photo — the API writes straight from
    request.FILES, so ImageField (Pillow) + extension allowlist are the only checks.
    """

    image = serializers.ImageField(
        validators=[FileExtensionValidator(ALLOWED_REVIEW_IMAGE_EXTENSIONS)]
    )

    def validate_image(self, value):
        if value.size > MAX_REVIEW_IMAGE_BYTES:
            mb = MAX_REVIEW_IMAGE_BYTES // (1024 * 1024)
            raise serializers.ValidationError(f"Each photo must be under {mb} MB.")
        return value


class ReviewSerializer(serializers.ModelSerializer):
    images = ReviewImageSerializer(many=True, read_only=True)
    helpful_by_me = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = (
            "id", "rating", "title", "body", "author_name",
            "verified_purchase", "helpful_count", "helpful_by_me", "is_mine",
            "images", "created_at",
        )
        read_only_fields = (
            "id", "author_name", "created_at",
            "verified_purchase", "helpful_count",
        )

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be 1-5.")
        return value

    def get_helpful_by_me(self, obj):
        # Anonymous callers get False, not null.
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        voted = getattr(obj, "voted_by_me", None)
        if voted is not None:
            return bool(voted)  # annotated by the list view; no extra query
        return obj.votes.filter(user=request.user).exists()

    def get_is_mine(self, obj):
        # Lets the UI hide the helpful control on your own review.
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.user_id == request.user.id
