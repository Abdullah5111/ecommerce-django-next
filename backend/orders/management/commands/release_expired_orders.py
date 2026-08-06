from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from orders import transitions
from orders.models import Order


class Command(BaseCommand):
    help = (
        "Cancel PENDING orders older than PENDING_ORDER_TTL_MINUTES so the stock "
        "they reserved (and any coupon redemption) is released back. Intended to "
        "run on a schedule (cron)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=None,
            help="Override PENDING_ORDER_TTL_MINUTES for this run.",
        )

    def handle(self, *args, **options):
        ttl = options["minutes"]
        if ttl is None:
            ttl = settings.PENDING_ORDER_TTL_MINUTES
        cutoff = timezone.now() - timedelta(minutes=ttl)

        stale = Order.objects.filter(status=Order.Status.PENDING, created_at__lt=cutoff)
        released = 0
        for order in stale:
            # cancel() restocks every line and deletes the coupon redemption; an
            # unpaid order takes the no-refund branch.
            transitions.cancel(order)
            released += 1

        self.stdout.write(f"Released {released} expired pending order(s).")
