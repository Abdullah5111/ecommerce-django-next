from django.conf import settings
from django.db import models

from orders.models import Order, OrderItem


class Return(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        RECEIVED = "received", "Received"
        REFUNDED = "refunded", "Refunded"
        REJECTED = "rejected", "Rejected"

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="returns")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    staff_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Return #{self.pk} for order #{self.order_id} ({self.status})"


class ReturnLine(models.Model):
    class Reason(models.TextChoices):
        DEFECTIVE = "defective", "Defective"
        WRONG_ITEM = "wrong_item", "Wrong item"
        NOT_AS_DESCRIBED = "not_as_described", "Not as described"
        NO_LONGER_NEEDED = "no_longer_needed", "No longer needed"
        OTHER = "other", "Other"

    return_request = models.ForeignKey(Return, on_delete=models.CASCADE, related_name="lines")
    order_item = models.ForeignKey(OrderItem, on_delete=models.PROTECT)
    quantity = models.PositiveSmallIntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    note = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.quantity}x item {self.order_item_id} ({self.reason})"
