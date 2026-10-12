"""Central fan-out for user notifications.

``notify()`` records an in-app Notification, emails, and web-pushes — best-effort
on the side channels, so a failed email/push never breaks the caller. Order
transitions call ``notify_order()`` from ``on_commit`` (never on a rollback).

The in-app row is written synchronously; email + push are Celery tasks queued
after commit (RabbitMQ when a broker is configured, inline otherwise).
"""
import logging

from asgiref.sync import async_to_sync
from django.db import transaction

from . import push, tasks
from .models import Notification

logger = logging.getLogger(__name__)


def notify(user, kind, title, body="", order=None, email=True):
    """Create a Notification and fan out to websocket + email + web push (best-effort)."""
    notification = Notification.objects.create(
        user=user, kind=kind, title=title, body=body, order=order
    )
    _broadcast(notification)
    if email and user.email:
        _enqueue(tasks.send_notification_email, notification.id)
    if push.is_enabled():
        _enqueue(tasks.send_notification_push, notification.id)
    return notification


def _enqueue(task, notification_id):
    """Queue ``task`` once the row is committed. If the broker is unreachable,
    deliver inline rather than drop the notification.
    """
    def _send():
        try:
            task.delay(notification_id)
        except Exception:
            logger.exception("Broker unavailable; running %s inline", task.name)
            task.apply(args=[notification_id])

    transaction.on_commit(_send)


def _broadcast(notification):
    """Push the new notification to its owner's websocket group (best-effort).

    Runs synchronously on the caller thread (notify() is invoked from
    on_commit callbacks, which execute on the worker thread), so
    async_to_sync is safe in every context that reaches us.
    """
    try:
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        if layer is None:
            return
        async_to_sync(layer.group_send)(
            f"user_{notification.user_id}",
            {
                "type": "notification",
                "json": {
                    "type": "notification",
                    "notification": {
                        "id": notification.id,
                        "kind": notification.kind,
                        "title": notification.title,
                        "body": notification.body,
                        "order": notification.order_id,
                        "is_read": notification.is_read,
                        "created_at": notification.created_at.isoformat(),
                    },
                    "unread_count": Notification.objects.filter(
                        user_id=notification.user_id, is_read=False
                    ).count(),
                },
            },
        )
    except Exception:  # never let the socket layer break the caller
        logger.exception("Websocket fan-out failed for notification %s", notification.pk)


# --- Order-event copy -------------------------------------------------------

def _order_message(order, kind):
    oid = order.id
    if kind == Notification.Kind.ORDER_PAID:
        return f"Order #{oid} confirmed", f"Thanks! We've received your payment of ${order.total}."
    if kind == Notification.Kind.ORDER_SHIPPED:
        detail = ""
        if order.tracking_carrier or order.tracking_number:
            carrier = order.tracking_carrier or "carrier"
            detail = f" Tracking: {carrier} {order.tracking_number}".rstrip()
        return f"Order #{oid} shipped", f"Your order is on its way.{detail}"
    if kind == Notification.Kind.ORDER_DELIVERED:
        return f"Order #{oid} delivered", "Your order has been delivered. Enjoy!"
    if kind == Notification.Kind.ORDER_CANCELLED:
        note = " A refund has been issued." if order.refunded_total else ""
        return f"Order #{oid} cancelled", f"Your order was cancelled.{note}"
    if kind == Notification.Kind.ORDER_REFUNDED:
        word = "partial refund" if order.status == "partially_refunded" else "refund"
        return f"Order #{oid} refunded", f"A {word} of ${order.refunded_total} has been processed."
    return f"Order #{oid} updated", ""


def notify_order(order, kind):
    """Build copy for an order event and notify its owner."""
    title, body = _order_message(order, kind)
    notify(order.user, kind, title, body, order=order)
