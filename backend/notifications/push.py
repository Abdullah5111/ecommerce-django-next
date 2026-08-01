"""Web Push (VAPID) delivery, a graceful no-op when keys are absent.

Enabled only with both VAPID keys set; otherwise push is skipped (in-app + email
still work). ``pywebpush`` is imported lazily.
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    return bool(
        getattr(settings, "VAPID_PUBLIC_KEY", "")
        and getattr(settings, "VAPID_PRIVATE_KEY", "")
    )


def public_key() -> str:
    return getattr(settings, "VAPID_PUBLIC_KEY", "")


def _vapid_claims() -> dict:
    return {"sub": f"mailto:{getattr(settings, 'VAPID_ADMIN_EMAIL', 'admin@example.com')}"}


def send(subscription, payload: dict) -> bool:
    """Deliver one push message; returns True on success.
    A dead subscription (404/410) is pruned here.
    """
    if not is_enabled():
        return False
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info=subscription.as_webpush_info(),
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims=dict(_vapid_claims()),
        )
        return True
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (404, 410):
            subscription.delete()  # gone for good — prune it
        else:
            logger.warning("Web push failed (%s): %s", status, exc)
        return False
