from django.db import transaction
from django.db.models import F
from rest_framework import serializers

from accounts.models import Address
from coupons.models import Coupon, CouponRedemption
from products.models import Product, ProductVariant
from .models import Order, OrderItem, OrderEvent
from .pricing import Line, quote


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    variant = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = OrderItem
        fields = (
            "id", "product", "product_name", "variant", "variant_sku",
            "variant_label", "quantity", "unit_price", "subtotal",
        )
        read_only_fields = ("unit_price", "variant_sku", "variant_label")


class OrderEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.username", read_only=True, default=None)

    class Meta:
        model = OrderEvent
        fields = ("id", "message", "to_status", "actor_name", "created_at")


class ShipInputSerializer(serializers.Serializer):
    tracking_number = serializers.CharField(required=False, allow_blank=True)
    tracking_carrier = serializers.CharField(required=False, allow_blank=True)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    events = OrderEventSerializer(many=True, read_only=True)
    shipping_address = serializers.CharField(required=False, allow_blank=True)
    shipping_address_id = serializers.PrimaryKeyRelatedField(
        queryset=Address.objects.none(), write_only=True, required=False
    )
    coupon_code = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Order
        fields = (
            "id", "status", "shipping_address", "shipping_address_id",
            "ship_recipient", "ship_phone", "ship_line1", "ship_line2",
            "ship_city", "ship_state", "ship_postal_code", "ship_country",
            "subtotal", "discount_total", "tax_total", "shipping_total", "coupon_code",
            "paid_at", "shipped_at", "delivered_at", "cancelled_at",
            "tracking_number", "tracking_carrier", "refunded_total",
            "payment_intent_id", "total", "items", "events", "created_at",
        )
        read_only_fields = (
            "status", "subtotal", "discount_total", "tax_total", "shipping_total", "total",
            "paid_at", "shipped_at", "delivered_at", "cancelled_at",
            "tracking_number", "tracking_carrier", "refunded_total",
            "payment_intent_id", "created_at",
            "ship_recipient", "ship_phone", "ship_line1", "ship_line2",
            "ship_city", "ship_state", "ship_postal_code", "ship_country",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request") if hasattr(self, "context") else None
        if request is not None and request.user.is_authenticated:
            self.fields["shipping_address_id"].queryset = Address.objects.filter(user=request.user)

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

        user = self.context["request"].user

        # Resolve + lock the coupon (if any) so the redemption count is race-safe.
        code = (validated_data.pop("coupon_code", "") or "").strip().upper()
        coupon = None
        if code:
            coupon = Coupon.objects.select_for_update().filter(code=code).first()
            if coupon is None:
                raise serializers.ValidationError({"coupon_code": "Invalid coupon code."})

        # Copy the chosen saved address into the order's snapshot fields.
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

        # Validate each variant belongs to its product, then build priced lines.
        lines = []
        for it in items_data:
            product = it["product"]
            variant = it.get("variant")
            if variant is not None:
                if variant.product_id != product.id:
                    raise serializers.ValidationError(
                        {"items": f"Variant {variant.sku} does not belong to {product.name}."}
                    )
                if not variant.is_active:
                    raise serializers.ValidationError(
                        {"items": f"Variant {variant.sku} is not available."}
                    )
            elif product.variants.filter(is_active=True).exists():
                # A variant product must be bought through a variant.
                raise serializers.ValidationError(
                    {"items": f"Select a variant for {product.name}."}
                )
            lines.append(Line(product, it["quantity"], variant))

        # Authoritative pricing (re-validates the coupon under the lock).
        price = quote(lines, coupon, user)
        if coupon is not None and price.coupon_error:
            raise serializers.ValidationError({"coupon_code": price.coupon_error})

        order = Order.objects.create(
            user=user,
            subtotal=price.subtotal,
            discount_total=price.discount_total,
            tax_total=price.tax_total,
            shipping_total=price.shipping_total,
            total=price.grand_total,
            coupon=coupon,
            coupon_code=(coupon.code if coupon else ""),
            **order_kwargs,
            **validated_data,
        )

        for line in lines:
            product = line.product
            variant = line.variant
            quantity = line.quantity
            if variant is not None:
                # Atomic conditional decrement — no-oversell, same as the product path.
                updated = ProductVariant.objects.filter(
                    pk=variant.pk, stock__gte=quantity
                ).update(stock=F("stock") - quantity)
                if not updated:
                    raise serializers.ValidationError(
                        {"items": f"Not enough stock for {product.name} ({variant.label})."}
                    )
            else:
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
                variant=variant,
                variant_sku=(variant.sku if variant else ""),
                variant_label=(variant.label if variant else ""),
                quantity=quantity,
                unit_price=line.unit_price,
            )

        if coupon is not None:
            CouponRedemption.objects.create(
                coupon=coupon, user=user, order=order, discount_amount=price.discount_total
            )

        return order
