"""Celery tasks for the notification side channels (email, web push).

Tasks take a Notification id, not model objects, so they serialize as JSON and
read committed state when the worker picks them up.
"""
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from . import push
from .models import Notification

logger = logging.getLogger(__name__)


def _load(notification_id):
    return (
        Notification.objects.select_related("user", "order")
        .filter(pk=notification_id)
        .first()
    )


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def send_notification_email(self, notification_id):
    n = _load(notification_id)
    if n is None or not n.user.email:
        return
    text = n.body or n.title
    if n.order_id is not None:
        text += f"\n\nView your order: {settings.FRONTEND_URL}/orders/{n.order_id}"
    # Raise on SMTP errors so autoretry backs off and tries again.
    send_mail(n.title, text, settings.DEFAULT_FROM_EMAIL, [n.user.email])


@shared_task
def send_notification_push(notification_id):
    # Not retried: a retry would re-push to subscriptions that already got it.
    n = _load(notification_id)
    if n is None or not push.is_enabled():
        return
    payload = {
        "title": n.title,
        "body": n.body,
        "url": f"/orders/{n.order_id}" if n.order_id is not None else "/account/notifications",
    }
    for sub in n.user.push_subscriptions.all():
        try:
            push.send(sub, payload)
        except Exception:  # never let a bad subscription break the rest
            logger.exception("Unexpected error pushing to subscription %s", sub.pk)
