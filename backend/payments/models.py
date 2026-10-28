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
