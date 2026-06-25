from django.db import transaction
from django.db.models import F
from django.utils import timezone

from products.models import Product
from .models import Order, OrderEvent

ALLOWED_TRANSITIONS = {
    Order.Status.PENDING: {Order.Status.PAID, Order.Status.CANCELLED},
    Order.Status.PAID: {Order.Status.SHIPPED, Order.Status.CANCELLED},
    Order.Status.SHIPPED: {Order.Status.DELIVERED},
    Order.Status.DELIVERED: set(),
    Order.Status.CANCELLED: set(),
    Order.Status.PARTIALLY_REFUNDED: set(),
    Order.Status.REFUNDED: set(),
}


class TransitionError(Exception):
    """Raised when an order status change is not allowed."""


def _check(order, to_status):
    if to_status not in ALLOWED_TRANSITIONS.get(order.status, set()):
        raise TransitionError(f"Cannot move order from '{order.status}' to '{to_status}'.")


def log_event(order, actor, message, to_status=""):
    OrderEvent.objects.create(order=order, actor=actor, message=message, to_status=to_status)


def _notify(order, key):
    """Queue a user notification for after the transaction commits.

    `key` is a short order-event name; deferring to on_commit guarantees we
    never notify on a rolled-back transition.
    """
    from notifications.models import Notification
    from notifications.service import notify_order

    kind = {
        "paid": Notification.Kind.ORDER_PAID,
        "shipped": Notification.Kind.ORDER_SHIPPED,
        "delivered": Notification.Kind.ORDER_DELIVERED,
        "cancelled": Notification.Kind.ORDER_CANCELLED,
        "refunded": Notification.Kind.ORDER_REFUNDED,
    }[key]
    transaction.on_commit(lambda: notify_order(order, kind))


@transaction.atomic
def mark_paid(order, actor=None):
    order = Order.objects.select_for_update().get(pk=order.pk)
    _check(order, Order.Status.PAID)
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=["status", "paid_at", "updated_at"])
    log_event(order, actor, "Payment received", Order.Status.PAID)
    _notify(order, "paid")
    return order


@transaction.atomic
def ship(order, actor=None, tracking_number="", tracking_carrier=""):
    order = Order.objects.select_for_update().get(pk=order.pk)
    _check(order, Order.Status.SHIPPED)
    order.status = Order.Status.SHIPPED
    order.shipped_at = timezone.now()
    order.tracking_number = tracking_number
    order.tracking_carrier = tracking_carrier
    order.save(update_fields=[
        "status", "shipped_at", "tracking_number", "tracking_carrier", "updated_at",
    ])
    detail = " via " + tracking_carrier if tracking_carrier else ""
    detail += f" ({tracking_number})" if tracking_number else ""
    log_event(order, actor, ("Shipped" + detail).strip(), Order.Status.SHIPPED)
    _notify(order, "shipped")
    return order


@transaction.atomic
def deliver(order, actor=None):
    order = Order.objects.select_for_update().get(pk=order.pk)
    _check(order, Order.Status.DELIVERED)
    order.status = Order.Status.DELIVERED
    order.delivered_at = timezone.now()
    order.save(update_fields=["status", "delivered_at", "updated_at"])
    log_event(order, actor, "Delivered", Order.Status.DELIVERED)
    _notify(order, "delivered")
    return order


@transaction.atomic
def cancel(order, actor=None):
    order = Order.objects.select_for_update().get(pk=order.pk)
    _check(order, Order.Status.CANCELLED)
    was_paid = order.status == Order.Status.PAID
    for item in order.items.all():
        Product.objects.filter(pk=item.product_id).update(stock=F("stock") + item.quantity)
    from coupons.models import CouponRedemption
    CouponRedemption.objects.filter(order=order).delete()
    update_fields = ["status", "cancelled_at", "updated_at"]
    refund_id = ""
    if was_paid:
        from payments import gateway
        refund_id = gateway.create_refund(order, order.total)
        order.refunded_total = order.total
        update_fields.append("refunded_total")
    order.status = Order.Status.CANCELLED
    order.cancelled_at = timezone.now()
    order.save(update_fields=update_fields)
    message = "Cancelled and refunded" if was_paid else "Cancelled"
    if refund_id:
        message += f" ({refund_id})"
    log_event(order, actor, message, Order.Status.CANCELLED)
    _notify(order, "cancelled")
    return order
