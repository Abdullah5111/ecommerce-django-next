from django.contrib import admin, messages

from . import transitions
from .models import Order, OrderItem, OrderEvent


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


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total", "refunded_total", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username", "user__email")
    inlines = [OrderItemInline, OrderEventInline]
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
