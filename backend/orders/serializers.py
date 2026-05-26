from django.db import transaction
from rest_framework import serializers

from products.models import Product
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "product", "product_name", "quantity", "unit_price", "subtotal")
        read_only_fields = ("unit_price",)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = ("id", "status", "shipping_address", "total", "items", "created_at")
        read_only_fields = ("status", "total", "created_at")

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")
        if not items_data:
            raise serializers.ValidationError({"items": "At least one item is required."})

        order = Order.objects.create(user=self.context["request"].user, **validated_data)
        for item_data in items_data:
            product = item_data["product"]
            quantity = item_data["quantity"]
            if product.stock < quantity:
                raise serializers.ValidationError(
                    {"items": f"Not enough stock for {product.name}."}
                )
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=product.price,
            )
            product.stock -= quantity
            product.save(update_fields=["stock"])

        order.recalculate_total()
        return order
