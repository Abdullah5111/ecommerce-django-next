"""Payment gateway abstraction over Stripe.

Without ``STRIPE_SECRET_KEY`` every call degrades to a deterministic mock mode
so checkout works end-to-end keyless; ``stripe`` is imported lazily.
"""
from decimal import Decimal

from django.conf import settings

MOCK_INTENT_PREFIX = "mock_pi_"


def is_live() -> bool:
    """True when a real Stripe secret key is configured."""
    return bool(getattr(settings, "STRIPE_SECRET_KEY", ""))


def _stripe():
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def to_cents(amount) -> int:
    """Convert a decimal money amount to an integer minor-unit (cents)."""
    return int((Decimal(amount) * 100).quantize(Decimal("1")))


def create_payment_intent(order):
    """Create a PaymentIntent for an order's grand total.

    Returns ``(client_secret, payment_intent_id, mock)``.
    """
    # A $0 order (e.g. a 100%-off coupon) has nothing to charge, and Stripe
    # rejects a zero-amount intent — settle it through the mock path regardless
    # of mode so the client's mock branch finalizes it.
    if not is_live() or to_cents(order.total) <= 0:
        pi_id = f"{MOCK_INTENT_PREFIX}{order.pk}"
        return f"{pi_id}_secret_mock", pi_id, True

    stripe = _stripe()
    intent = stripe.PaymentIntent.create(
        amount=to_cents(order.total),
        currency=settings.STRIPE_CURRENCY,
        metadata={"order_id": str(order.pk)},
        automatic_payment_methods={"enabled": True},
    )
    return intent.client_secret, intent.id, False


def verify_paid(order):
    """Confirm an order's PaymentIntent actually succeeded.

    Returns ``(ok, detail)``. In mock mode payment is always considered good.
    """
    # Mock mode, or a $0 order that never had a real intent, is paid by definition.
    if not is_live() or to_cents(order.total) <= 0:
        return True, ""
    if not order.payment_intent_id:
        return False, "No payment intent for this order."
    stripe = _stripe()
    intent = stripe.PaymentIntent.retrieve(order.payment_intent_id)
    if intent.status == "succeeded":
        return True, ""
    return False, f"Payment not completed (status: {intent.status})."


def create_refund(order, amount) -> str:
    """Refund ``amount`` against the order's PaymentIntent. Returns a refund id.

    No-ops (returns "") for non-positive amounts. Falls back to a mock refund id
    when not live or when the order was paid via the mock path.
    """
    cents = to_cents(amount)
    if cents <= 0:
        return ""
    intent_id = order.payment_intent_id or ""
    if not is_live() or not intent_id or intent_id.startswith(MOCK_INTENT_PREFIX):
        return f"mock_re_{order.pk}"
    stripe = _stripe()
    refund = stripe.Refund.create(payment_intent=intent_id, amount=cents)
    return refund.id


def construct_event(payload: bytes, sig_header: str):
    """Verify a Stripe webhook signature and return the parsed event.

    Raises ``ValueError`` on a bad payload or signature.
    """
    stripe = _stripe()
    try:
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as exc:  # invalid payload or signature
        raise ValueError(str(exc)) from exc
