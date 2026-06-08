from django.db import transaction
from django.db.models import F
from rest_framework import serializers

from accounts.models import Address
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
    shipping_address = serializers.CharField(required=False, allow_blank=True)
    shipping_address_id = serializers.PrimaryKeyRelatedField(
        queryset=Address.objects.none(), write_only=True, required=False
    )

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "shipping_address",
            "shipping_address_id",
            "ship_recipient",
            "ship_phone",
            "ship_line1",
            "ship_line2",
            "ship_city",
            "ship_state",
            "ship_postal_code",
            "ship_country",
            "total",
            "items",
            "created_at",
        )
        read_only_fields = (
            "status",
            "total",
            "created_at",
            "ship_recipient",
            "ship_phone",
            "ship_line1",
            "ship_line2",
            "ship_city",
            "ship_state",
            "ship_postal_code",
            "ship_country",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request") if hasattr(self, "context") else None
        if request is not None and request.user.is_authenticated:
            self.fields["shipping_address_id"].queryset = Address.objects.filter(
                user=request.user
            )

    def validate(self, attrs):
        if not attrs.get("shipping_address_id") and not attrs.get("shipping_address"):
            raise serializers.ValidationError(
                {"shipping_address": "Provide shipping_address_id or shipping_address."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")
        if not items_data:
            raise serializers.ValidationError({"items": "At least one item is required."})

        address = validated_data.pop("shipping_address_id", None)
        order_kwargs = {}
        if address is not None:
            order_kwargs["shipping_address"] = address.as_text()
            order_kwargs["ship_recipient"] = address.recipient
            order_kwargs["ship_phone"] = address.phone
            order_kwargs["ship_line1"] = address.line1
            order_kwargs["ship_line2"] = address.line2
            order_kwargs["ship_city"] = address.city
            order_kwargs["ship_state"] = address.state
            order_kwargs["ship_postal_code"] = address.postal_code
            order_kwargs["ship_country"] = address.country
            validated_data.pop("shipping_address", None)
        else:
            order_kwargs["shipping_address"] = validated_data.pop("shipping_address")

        order = Order.objects.create(
            user=self.context["request"].user, **order_kwargs, **validated_data
        )
        for item_data in items_data:
            product = item_data["product"]
            quantity = item_data["quantity"]
            updated = Product.objects.filter(
                pk=product.pk, stock__gte=quantity
            ).update(stock=F("stock") - quantity)
            if not updated:
                raise serializers.ValidationError(
                    {"items": f"Not enough stock for {product.name}."}
                )
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=product.price,
            )

        order.recalculate_total()
        return order
