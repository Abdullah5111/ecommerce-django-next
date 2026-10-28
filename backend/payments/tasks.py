from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from payments.models import StripeEvent

# Stripe stops retrying an event after three days; keep a margin past that.
EVENT_RETENTION_DAYS = 30


@shared_task
def prune_stripe_events(days=EVENT_RETENTION_DAYS):
    """Drop handled-event records old enough that Stripe can't redeliver them."""
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = StripeEvent.objects.filter(created_at__lt=cutoff).delete()
    return deleted
