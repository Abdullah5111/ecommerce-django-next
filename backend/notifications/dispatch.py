"""Run best-effort side-channel work (email, web push) off the request path.

Order transitions call ``notify`` from an ``on_commit`` hook that runs inside the
web worker; delivering email + push there blocks the response on network I/O. This
hands that work to a small bounded thread pool instead — no broker, no new
dependency. It is opt-in via ``NOTIFICATIONS_ASYNC`` so tests (and anyone who
wants deterministic inline delivery) keep the synchronous path.

Delivery is best-effort: a failed send is logged, never retried. If you need
at-least-once delivery, reach for a real task queue (Celery/RQ) instead.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import connections

logger = logging.getLogger(__name__)

_executor = None


def _get_executor() -> ThreadPoolExecutor:
    # One pool per worker process, created on first async use.
    global _executor
    if _executor is None:
        workers = getattr(settings, "NOTIFICATIONS_WORKERS", 4)
        _executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="notify")
    return _executor


def run(func, *args, **kwargs):
    """Run ``func`` for its side effects. Inline unless ``NOTIFICATIONS_ASYNC``.

    Returns the ``Future`` in async mode (handy for tests) or ``None`` inline.
    """
    if not getattr(settings, "NOTIFICATIONS_ASYNC", False):
        func(*args, **kwargs)
        return None

    def _task():
        try:
            func(*args, **kwargs)
        except Exception:  # best-effort: a bad send must not crash the worker
            logger.exception("Notification side-channel task failed")
        finally:
            connections.close_all()  # a background thread owns its own DB connections

    return _get_executor().submit(_task)
