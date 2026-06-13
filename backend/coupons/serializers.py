from rest_framework import serializers

from products.models import Product


class QuoteItemSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)


class CouponQuoteSerializer(serializers.Serializer):
    code = serializers.CharField(required=False, allow_blank=True)
    items = QuoteItemSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        return value
