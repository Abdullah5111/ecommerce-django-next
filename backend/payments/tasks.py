import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from payments import gateway
from payments.models import Refund, StripeEvent

logger = logging.getLogger(__name__)

# Stripe stops retrying an event after three days; keep a margin past that.
EVENT_RETENTION_DAYS = 30
# Failed Stripe calls before a refund is marked failed for staff to handle.
REFUND_MAX_ATTEMPTS = 5
# A pending refund untouched this long is assumed lost (worker crash, broker
# down at enqueue) and re-queued by the sweep.
REFUND_STALE_AFTER = timedelta(minutes=2)


@shared_task
def prune_stripe_events(days=EVENT_RETENTION_DAYS):
    """Drop handled-event records old enough that Stripe can't redeliver them."""
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = StripeEvent.objects.filter(created_at__lt=cutoff).delete()
    return deleted


@shared_task
def issue_refund(refund_id):
    """Send one pending refund to Stripe.

    The row lock keeps two workers off the same refund, and the stored
    idempotency key makes a repeat call return Stripe's existing refund — so
    a crash after Stripe succeeded but before the save just leaves the row
    pending for the sweep to finish.
    """
    from orders.transitions import log_event

    with transaction.atomic():
        refund = (
            Refund.objects.select_for_update()
            .select_related("order")
            .filter(pk=refund_id, status=Refund.Status.PENDING)
            .first()
        )
        if refund is None:
            return
        refund.attempts += 1
        try:
            refund_id_at_stripe = gateway.create_refund(
                refund.order, refund.amount, idempotency_key=refund.idempotency_key
            )
        except Exception as exc:
            logger.exception("Refund %s failed (attempt %s)", refund.pk, refund.attempts)
            refund.last_error = str(exc)[:255]
            if refund.attempts >= REFUND_MAX_ATTEMPTS:
                refund.status = Refund.Status.FAILED
                log_event(
                    refund.order, None,
                    f"Refund of ${refund.amount} failed after {refund.attempts} attempts "
                    "and needs staff attention",
                )
            refund.save(update_fields=["attempts", "last_error", "status", "updated_at"])
            return
        refund.status = Refund.Status.SUCCEEDED
        refund.stripe_refund_id = refund_id_at_stripe
        refund.last_error = ""
        refund.save(update_fields=[
            "attempts", "status", "stripe_refund_id", "last_error", "updated_at",
        ])
        log_event(refund.order, None, f"Refund of ${refund.amount} issued ({refund_id_at_stripe})")


@shared_task
def retry_pending_refunds():
    """Re-queue refunds stuck in pending: failed attempts under the limit, or
    ones whose task never ran."""
    cutoff = timezone.now() - REFUND_STALE_AFTER
    pending = Refund.objects.filter(status=Refund.Status.PENDING, updated_at__lt=cutoff)
    ids = list(pending.values_list("pk", flat=True))
    for pk in ids:
        issue_refund.delay(pk)
    return len(ids)
