from django.core.management.base import BaseCommand

from payments.tasks import EVENT_RETENTION_DAYS, prune_stripe_events


class Command(BaseCommand):
    help = (
        "Delete handled Stripe webhook event records older than the retention "
        "window. Celery Beat runs this daily; the command is for scheduled jobs "
        "and running it by hand."
    )

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=EVENT_RETENTION_DAYS)

    def handle(self, *args, **options):
        deleted = prune_stripe_events(options["days"])
        self.stdout.write(f"Deleted {deleted} Stripe event record(s).")
