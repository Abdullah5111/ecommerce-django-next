from django.db import transaction
from django.db.models import F, Sum
from decimal import Decimal
from django.utils import timezone

from orders.models import Order
from orders.transitions import log_event
from products.models import Product

from .models import Return, ReturnLine
from .refunds import refund_for

ALLOWED = {
    Return.Status.REQUESTED: {Return.Status.APPROVED, Return.Status.REJECTED},
    Return.Status.APPROVED: {Return.Status.RECEIVED, Return.Status.REJECTED},
    Return.Status.RECEIVED: {Return.Status.REFUNDED},
    Return.Status.REFUNDED: set(),
    Return.Status.REJECTED: set(),
}


class ReturnTransitionError(Exception):
    """Raised when a return status change is not allowed."""


def _check(ret, to_status):
    if to_status not in ALLOWED.get(ret.status, set()):
        raise ReturnTransitionError(f"Cannot move return from '{ret.status}' to '{to_status}'.")


@transaction.atomic
def approve(ret, actor=None):
    ret = Return.objects.select_for_update().get(pk=ret.pk)
    _check(ret, Return.Status.APPROVED)
    ret.status = Return.Status.APPROVED
    ret.decided_at = timezone.now()
    ret.save(update_fields=["status", "decided_at"])
    log_event(ret.order, actor, f"Return #{ret.id} approved")
    return ret


@transaction.atomic
def reject(ret, actor=None, staff_note=""):
    ret = Return.objects.select_for_update().get(pk=ret.pk)
    _check(ret, Return.Status.REJECTED)
    ret.status = Return.Status.REJECTED
    ret.decided_at = timezone.now()
    ret.staff_note = staff_note
    ret.save(update_fields=["status", "decided_at", "staff_note"])
    log_event(ret.order, actor, f"Return #{ret.id} rejected")
    return ret


@transaction.atomic
def receive(ret, actor=None):
    ret = Return.objects.select_for_update().get(pk=ret.pk)
    _check(ret, Return.Status.RECEIVED)
    for line in ret.lines.select_related("order_item"):
        Product.objects.filter(pk=line.order_item.product_id).update(
            stock=F("stock") + line.quantity
        )
    ret.status = Return.Status.RECEIVED
    ret.received_at = timezone.now()
    ret.save(update_fields=["status", "received_at"])
    log_event(ret.order, actor, f"Return #{ret.id} items received and restocked")
    return ret


@transaction.atomic
def refund(ret, actor=None):
    ret = Return.objects.select_for_update().get(pk=ret.pk)
    _check(ret, Return.Status.REFUNDED)
    order = Order.objects.select_for_update().get(pk=ret.order_id)

    amount = refund_for(ret)
    # Never refund more than the customer actually paid (subtotal − discount),
    # cumulatively across all of this order's returns. Shipping is never refunded.
    max_refundable = order.subtotal - order.discount_total - order.refunded_total
    if max_refundable < 0:
        max_refundable = Decimal("0")
    if amount > max_refundable:
        amount = max_refundable

    from payments import gateway
    refund_id = gateway.create_refund(order, amount)

    ret.refund_amount = amount
    ret.status = Return.Status.REFUNDED
    ret.refunded_at = timezone.now()
    ret.save(update_fields=["status", "refund_amount", "refunded_at"])

    order.refunded_total = order.refunded_total + amount
    purchased_units = sum(i.quantity for i in order.items.all())
    refunded_units = (
        ReturnLine.objects.filter(
            return_request__order=order,
            return_request__status=Return.Status.REFUNDED,
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
    )
    order.status = (
        Order.Status.REFUNDED if refunded_units >= purchased_units
        else Order.Status.PARTIALLY_REFUNDED
    )
    order.save(update_fields=["refunded_total", "status", "updated_at"])
    suffix = f" ({refund_id})" if refund_id else ""
    log_event(order, actor, f"Return #{ret.id} refunded ${amount}{suffix}", order.status)

    from notifications.models import Notification
    from notifications.service import notify_order
    transaction.on_commit(lambda: notify_order(order, Notification.Kind.ORDER_REFUNDED))
    return ret
