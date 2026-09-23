from rest_framework import serializers

from products.models import Product, ProductVariant


class QuoteItemSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    variant = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(), required=False, allow_null=True
    )
    quantity = serializers.IntegerField(min_value=1)


class CouponQuoteSerializer(serializers.Serializer):
    code = serializers.CharField(required=False, allow_blank=True)
    items = QuoteItemSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        return value
