from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from orders import transitions
from orders.models import Order


@shared_task
def release_expired_orders(minutes=None):
    """Cancel PENDING orders older than the TTL so their reserved stock (and any
    coupon redemption) goes back. Run every few minutes by Celery Beat.
    """
    ttl = settings.PENDING_ORDER_TTL_MINUTES if minutes is None else minutes
    cutoff = timezone.now() - timedelta(minutes=ttl)

    released = 0
    for order in Order.objects.filter(status=Order.Status.PENDING, created_at__lt=cutoff):
        # An order that raced to PAID (or was already cancelled) since the query
        # fails cancel()'s state check — skip it instead of aborting the batch.
        try:
            transitions.cancel(order)
        except transitions.TransitionError:
            continue
        released += 1
    return released
