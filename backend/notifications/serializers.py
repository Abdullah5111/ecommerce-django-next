from rest_framework import serializers

from .models import Notification, PushSubscription


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "kind", "title", "body", "order", "is_read", "created_at")
        read_only_fields = fields


class PushSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushSubscription
        fields = ("endpoint", "p256dh", "auth")
        # View upserts by endpoint, so the unique validator must not block re-subscribe.
        extra_kwargs = {"endpoint": {"validators": []}}

    def to_internal_value(self, data):
        """Accept the browser's shape `{ endpoint, keys: { p256dh, auth } }` → flat fields."""
        if not isinstance(data, dict):
            # Dict-shaped so .errors (a ReturnDict) can render it; a bare string
            # makes self._errors a list and ReturnDict() then raises ValueError.
            raise serializers.ValidationError(
                {"non_field_errors": ["Expected an object with an endpoint and keys."]}
            )
        keys = data.get("keys") if isinstance(data.get("keys"), dict) else {}
        return super().to_internal_value({
            "endpoint": data.get("endpoint"),
            "p256dh": keys.get("p256dh", data.get("p256dh")),
            "auth": keys.get("auth", data.get("auth")),
        })
