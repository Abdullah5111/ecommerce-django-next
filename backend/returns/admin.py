from django.contrib import admin, messages

from . import services
from .models import Return, ReturnLine


class ReturnLineInline(admin.TabularInline):
    model = ReturnLine
    extra = 0
    readonly_fields = ("order_item", "quantity", "reason", "note")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Return)
class ReturnAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "status", "refund_amount", "created_at")
    list_filter = ("status",)
    search_fields = ("order__id", "requested_by__username")
    readonly_fields = ("order", "requested_by", "refund_amount",
                       "created_at", "decided_at", "received_at", "refunded_at")
    inlines = [ReturnLineInline]
    actions = ("approve_returns", "receive_returns", "refund_returns")

    @admin.action(description="Approve selected returns")
    def approve_returns(self, request, queryset):
        for ret in queryset:
            try:
                services.approve(ret, actor=request.user)
            except services.ReturnTransitionError:
                self.message_user(request, f"Return #{ret.id}: cannot approve from {ret.status}.", level=messages.WARNING)

    @admin.action(description="Mark received (restock)")
    def receive_returns(self, request, queryset):
        for ret in queryset:
            try:
                services.receive(ret, actor=request.user)
            except services.ReturnTransitionError:
                self.message_user(request, f"Return #{ret.id}: cannot receive from {ret.status}.", level=messages.WARNING)

    @admin.action(description="Refund selected returns")
    def refund_returns(self, request, queryset):
        for ret in queryset:
            try:
                services.refund(ret, actor=request.user)
            except services.ReturnTransitionError:
                self.message_user(request, f"Return #{ret.id}: cannot refund from {ret.status}.", level=messages.WARNING)
