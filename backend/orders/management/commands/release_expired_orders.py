from django.core.management.base import BaseCommand

from orders.tasks import release_expired_orders


class Command(BaseCommand):
    help = (
        "Cancel PENDING orders older than PENDING_ORDER_TTL_MINUTES so the stock "
        "they reserved is released. Celery Beat runs this on a schedule; the "
        "command is for running it by hand."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=None,
            help="Override PENDING_ORDER_TTL_MINUTES for this run.",
        )

    def handle(self, *args, **options):
        released = release_expired_orders(options["minutes"])
        self.stdout.write(f"Released {released} expired pending order(s).")
