from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from rest_framework import serializers

from orders.models import Order, OrderItem

from .models import Return, ReturnLine


class ReturnLineInputSerializer(serializers.Serializer):
    order_item = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    reason = serializers.ChoiceField(choices=ReturnLine.Reason.choices)
    note = serializers.CharField(required=False, allow_blank=True)


class ReturnLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="order_item.product.name", read_only=True)
    variant_label = serializers.CharField(source="order_item.variant_label", read_only=True)

    class Meta:
        model = ReturnLine
        fields = ("id", "order_item", "product_name", "variant_label", "quantity", "reason", "note")


class ReturnSerializer(serializers.ModelSerializer):
    lines = ReturnLineSerializer(many=True, read_only=True)

    class Meta:
        model = Return
        fields = (
            "id", "order", "status", "refund_amount", "staff_note",
            "created_at", "decided_at", "received_at", "refunded_at", "lines",
        )
        read_only_fields = (
            "status", "refund_amount", "staff_note",
            "created_at", "decided_at", "received_at", "refunded_at",
        )


class ReturnCreateSerializer(serializers.Serializer):
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all())
    lines = ReturnLineInputSerializer(many=True)

    def validate(self, attrs):
        request = self.context["request"]
        order = attrs["order"]
        if order.user_id != request.user.id:
            raise serializers.ValidationError({"order": "Not your order."})
        if order.status not in (Order.Status.DELIVERED, Order.Status.PARTIALLY_REFUNDED):
            raise serializers.ValidationError({"order": "Only delivered orders can be returned."})
        window = timedelta(days=settings.RETURN_WINDOW_DAYS)
        if not order.delivered_at or timezone.now() - order.delivered_at > window:
            raise serializers.ValidationError({"order": "Return window has closed."})
        if not attrs["lines"]:
            raise serializers.ValidationError({"lines": "At least one item is required."})

        self._assert_within_remaining(order, attrs["lines"])
        return attrs

    def _assert_within_remaining(self, order, lines):
        """Reject requesting more of an item than is still returnable. Run in
        validate() for early feedback and again in create() under a row lock, so
        two concurrent requests can't both pass on the same stale remaining count.
        """
        items = {i.id: i for i in order.items.all()}
        returned = {}
        for r in order.returns.exclude(status=Return.Status.REJECTED):
            for ln in r.lines.all():
                returned[ln.order_item_id] = returned.get(ln.order_item_id, 0) + ln.quantity

        # Sum requested quantities per item so duplicate lines for the same item
        # in one request can't each pass the remaining check independently.
        requested = {}
        for line in lines:
            requested[line["order_item"]] = requested.get(line["order_item"], 0) + line["quantity"]

        for oi_id, qty in requested.items():
            if oi_id not in items:
                raise serializers.ValidationError({"lines": f"Item {oi_id} is not on this order."})
            remaining = items[oi_id].quantity - returned.get(oi_id, 0)
            if qty > remaining:
                raise serializers.ValidationError(
                    {"lines": f"Item {oi_id}: only {remaining} unit(s) returnable."}
                )

    def create(self, validated_data):
        request = self.context["request"]
        order = validated_data["order"]
        with transaction.atomic():
            # Lock the order so concurrent return requests serialize; then
            # re-check remaining against now-committed returns before writing.
            Order.objects.select_for_update().get(pk=order.pk)
            self._assert_within_remaining(order, validated_data["lines"])
            ret = Return.objects.create(order=order, requested_by=request.user)
            for line in validated_data["lines"]:
                ReturnLine.objects.create(
                    return_request=ret,
                    order_item=OrderItem.objects.get(pk=line["order_item"]),
                    quantity=line["quantity"],
                    reason=line["reason"],
                    note=line.get("note", ""),
                )
            from orders.transitions import log_event
            log_event(order, request.user, f"Return #{ret.id} requested")
        return ret

    def to_representation(self, instance):
        return ReturnSerializer(instance, context=self.context).data
