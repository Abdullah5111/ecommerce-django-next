from django.core.management.base import BaseCommand

from payments.tasks import retry_pending_refunds


class Command(BaseCommand):
    help = (
        "Re-send refunds stuck in pending. Celery Beat runs this on a schedule; "
        "where there is no Beat (Cloud Run), a scheduled job runs the command."
    )

    def handle(self, *args, **options):
        queued = retry_pending_refunds()
        self.stdout.write(f"Re-queued {queued} pending refund(s).")
