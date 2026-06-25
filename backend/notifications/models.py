from django.conf import settings
from django.db import models


class Notification(models.Model):
    """An in-app notification for a single user, mirroring an order event."""

    class Kind(models.TextChoices):
        ORDER_PAID = "order_paid", "Order paid"
        ORDER_SHIPPED = "order_shipped", "Order shipped"
        ORDER_DELIVERED = "order_delivered", "Order delivered"
        ORDER_CANCELLED = "order_cancelled", "Order cancelled"
        ORDER_REFUNDED = "order_refunded", "Order refunded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    title = models.CharField(max_length=160)
    body = models.CharField(max_length=400, blank=True)
    order = models.ForeignKey(
        "orders.Order", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="notifications",
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read"])]

    def __str__(self):
        return f"{self.get_kind_display()} → {self.user}"


class PushSubscription(models.Model):
    """A browser Web Push subscription (one per device/browser per user)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    endpoint = models.URLField(max_length=600, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PushSubscription({self.user}, …{self.endpoint[-12:]})"

    def as_webpush_info(self):
        return {"endpoint": self.endpoint, "keys": {"p256dh": self.p256dh, "auth": self.auth}}
