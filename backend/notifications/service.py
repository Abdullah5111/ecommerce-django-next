"""Central fan-out for user notifications.

``notify()`` records an in-app Notification, emails, and web-pushes — best-effort
on the side channels, so a failed email/push never breaks the caller. Order
transitions call ``notify_order()`` from ``on_commit`` (never on a rollback).

The in-app row is written synchronously; email + push are handed to
``dispatch.run`` so they can leave the request path when ``NOTIFICATIONS_ASYNC``
is on (inline otherwise).
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

from . import dispatch, push
from .models import Notification

logger = logging.getLogger(__name__)


def notify(user, kind, title, body="", order=None, email=True):
    """Create a Notification and fan out to email + web push (best-effort)."""
    notification = Notification.objects.create(
        user=user, kind=kind, title=title, body=body, order=order
    )
    dispatch.run(_deliver, user, title, body, order, email)
    return notification


def _deliver(user, title, body, order, email):
    """The side-channel fan-out — runs inline or in a background thread."""
    if email and user.email:
        _send_email(user, title, body, order)
    _send_push(user, title, body, order)


def _send_email(user, title, body, order):
    text = body or title
    if order is not None:
        text += f"\n\nView your order: {settings.FRONTEND_URL}/orders/{order.id}"
    send_mail(title, text, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)


def _send_push(user, title, body, order):
    if not push.is_enabled():
        return
    payload = {
        "title": title,
        "body": body,
        "url": f"/orders/{order.id}" if order is not None else "/account/notifications",
    }
    for sub in user.push_subscriptions.all():
        try:
            push.send(sub, payload)
        except Exception:  # never let a bad subscription break the caller
            logger.exception("Unexpected error pushing to subscription %s", sub.pk)


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
