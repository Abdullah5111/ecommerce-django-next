from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from payments.models import Refund

from . import transitions
from .models import Order, OrderEvent, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    readonly_fields = ("message", "to_status", "actor", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class RefundInline(admin.TabularInline):
    """The order's refunds from the refund queue (payments.Refund), read-only.
    A failed one is retried from its own page (Payments → Refunds)."""

    model = Refund
    extra = 0
    can_delete = False
    fields = ("refund_link", "amount", "status", "attempts", "stripe_refund_id", "last_error")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Refund")
    def refund_link(self, refund):
        url = reverse("admin:payments_refund_change", args=[refund.pk])
        return format_html('<a href="{}">{}</a>', url, refund.idempotency_key)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total", "refunded_total", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username", "user__email")
    inlines = [OrderItemInline, RefundInline, OrderEventInline]
    actions = ("mark_shipped", "mark_delivered", "cancel_orders")

    @admin.action(description="Mark selected orders shipped")
    def mark_shipped(self, request, queryset):
        for order in queryset:
            try:
                transitions.ship(order, actor=request.user)
            except transitions.TransitionError:
                self.message_user(request, f"Order #{order.id}: cannot ship from {order.status}.", level=messages.WARNING)

    @admin.action(description="Mark selected orders delivered")
    def mark_delivered(self, request, queryset):
        for order in queryset:
            try:
                transitions.deliver(order, actor=request.user)
            except transitions.TransitionError:
                self.message_user(request, f"Order #{order.id}: cannot deliver from {order.status}.", level=messages.WARNING)

    @admin.action(description="Cancel selected orders")
    def cancel_orders(self, request, queryset):
        for order in queryset:
            try:
                transitions.cancel(order, actor=request.user)
            except transitions.TransitionError:
                self.message_user(request, f"Order #{order.id}: cannot cancel from {order.status}.", level=messages.WARNING)
