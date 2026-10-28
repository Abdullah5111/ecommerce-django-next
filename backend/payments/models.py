from django.db import models


class StripeEvent(models.Model):
    """A webhook event that has been handled. Stripe delivers at least once and
    retries for up to three days, so the unique id makes redelivery a no-op."""

    event_id = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.type} {self.event_id}"


class Refund(models.Model):
    """A refund the store owes, recorded in the same transaction as the cancel
    or return that causes it and issued to Stripe after commit
    (``payments.tasks.issue_refund``). A rollback takes the row with it, so
    Stripe never refunds something the database doesn't know about.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    # Names the business event (cancel-<order>, return-<return>); passed to
    # Stripe so a retried call can't refund twice.
    idempotency_key = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    stripe_refund_id = models.CharField(max_length=255, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Refund {self.idempotency_key} ({self.status})"
