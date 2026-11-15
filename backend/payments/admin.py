from django.contrib import admin, messages
from django.db import transaction

from orders.transitions import log_event

from . import gateway
from .models import Refund, StripeEvent


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    """The refund queue (payments.tasks.issue_refund). Read-only: amounts and
    keys are set by the cancel/return that owes the money. A refund that
    failed every attempt shows up under status=failed and can be retried."""

    list_display = (
        "id", "order", "amount", "status", "attempts", "stripe_refund_id",
        "last_error", "created_at",
    )
    list_filter = ("status",)
    search_fields = ("idempotency_key", "stripe_refund_id", "order__id")
    readonly_fields = (
        "order", "amount", "idempotency_key", "status", "stripe_refund_id",
        "attempts", "last_error", "created_at", "updated_at",
    )
    actions = ("retry_failed",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Retry selected failed refunds")
    def retry_failed(self, request, queryset):
        failed = list(queryset.filter(status=Refund.Status.FAILED).select_related("order"))
        for refund in failed:
            refund.status = Refund.Status.PENDING
            refund.attempts = 0
            refund.last_error = ""
            refund.save(update_fields=["status", "attempts", "last_error", "updated_at"])
            log_event(refund.order, request.user, f"Refund of ${refund.amount} retry requested")
            # Same idempotency key as before, so Stripe can't refund twice.
            transaction.on_commit(lambda pk=refund.pk: gateway._enqueue_refund(pk))
        skipped = queryset.count() - len(failed)
        self.message_user(request, f"Queued {len(failed)} refund(s) for another attempt.")
        if skipped:
            self.message_user(
                request, f"Skipped {skipped} that weren't failed.", level=messages.WARNING
            )


@admin.register(StripeEvent)
class StripeEventAdmin(admin.ModelAdmin):
    """Webhook events already handled (de-duplication record). Read-only."""

    list_display = ("event_id", "type", "created_at")
    list_filter = ("type",)
    search_fields = ("event_id",)
    readonly_fields = ("event_id", "type", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
