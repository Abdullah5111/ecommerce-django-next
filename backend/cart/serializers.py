from decimal import Decimal

from rest_framework import serializers

from products.serializers import ProductSerializer, ProductVariantSerializer

from .models import Cart, CartItem


def _line_unit_price(item):
    return item.variant.effective_price if item.variant_id else item.product.price


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    variant = ProductVariantSerializer(read_only=True)
    unit_price = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ("id", "product", "variant", "quantity", "unit_price")

    def get_unit_price(self, obj):
        return str(_line_unit_price(obj))


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ("id", "items", "total")

    def get_total(self, obj):
        total = sum(
            (_line_unit_price(i) * i.quantity for i in obj.items.all()), Decimal("0")
        )
        return str(total.quantize(Decimal("0.01")))
