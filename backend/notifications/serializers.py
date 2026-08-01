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
        keys = data.get("keys") or {}
        return super().to_internal_value({
            "endpoint": data.get("endpoint"),
            "p256dh": keys.get("p256dh", data.get("p256dh")),
            "auth": keys.get("auth", data.get("auth")),
        })
