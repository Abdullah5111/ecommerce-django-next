from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders import transitions
from orders.models import Order

from . import gateway
from .models import StripeEvent


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """Authoritative payment confirmation for live Stripe — moves the matching
    order to PAID on ``payment_intent.succeeded``, and mirrors refunds and
    disputes made in the Stripe dashboard onto the order. Verified and idempotent.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            event = gateway.construct_event(
                request.body, request.META.get("HTTP_STRIPE_SIGNATURE", "")
            )
        except ValueError:
            return HttpResponseBadRequest("Invalid payload or signature")

        # Record the event and handle it in one transaction: a redelivery finds
        # the row and stops, and a handler that fails rolls the row back so
        # Stripe's retry runs it again. Concurrent duplicates serialise on the
        # unique index.
        with transaction.atomic():
            event_id = event.get("id")
            if event_id:
                _, created = StripeEvent.objects.get_or_create(
                    event_id=event_id, defaults={"type": event["type"]}
                )
                if not created:
                    return HttpResponse(status=200)
            self._dispatch(event)

        return HttpResponse(status=200)

    def _dispatch(self, event):
        if event["type"] == "payment_intent.succeeded":
            intent = event["data"]["object"]
            order_id = (intent.get("metadata") or {}).get("order_id")
            self._mark_paid(intent.get("id"), order_id, intent.get("amount"))
        elif event["type"] == "charge.refunded":
            self._mirror_refund(event["data"]["object"])
        elif event["type"] in ("charge.dispute.created", "charge.dispute.closed"):
            self._log_dispute(event["type"], event["data"]["object"])

    def _mark_paid(self, intent_id, order_id, amount=None):
        order = None
        if order_id:
            order = Order.objects.filter(pk=order_id).first()
        if order is None and intent_id:
            order = Order.objects.filter(payment_intent_id=intent_id).first()
        if order is None:
            return
        if order.status != Order.Status.PENDING:
            self._refund_if_stray(order, intent_id, amount)
            return
        # Don't confirm against an intent that charged something other than the
        # order total (same guard the interactive pay path applies).
        if amount is not None and amount != gateway.to_cents(order.total):
            return
        # Persist the intent id when the order was resolved by metadata and never
        # stored one (e.g. paid on a Stripe-hosted page) — otherwise a later
        # refund can't find the intent and would silently skip the real refund.
        if intent_id and order.payment_intent_id != intent_id:
            order.payment_intent_id = intent_id
            order.save(update_fields=["payment_intent_id", "updated_at"])
        try:
            transitions.mark_paid(order)
        except transitions.TransitionError:
            pass

    def _refund_if_stray(self, order, intent_id, amount):
        """A succeeded intent for an order that isn't pending is money we must
        give back — unless it's the very intent the order was paid with (a
        redelivered event). Covers an order cancelled mid-payment (by the
        customer or the expiry job) and a second intent paid from a stale tab.
        """
        paid_with_this = order.paid_at is not None and order.payment_intent_id == intent_id
        if paid_with_this or not intent_id or not amount:
            return
        refund_id = gateway.refund_intent(intent_id, amount, f"stray-{intent_id}")
        transitions.log_event(
            order, None, f"Refunded stray payment {intent_id} ({refund_id})"
        )

    @transaction.atomic
    def _mirror_refund(self, charge):
        """Record refunds issued outside the store (e.g. the Stripe dashboard).

        ``amount_refunded`` is Stripe's running total for the charge, so only
        the part above ``order.refunded_total`` is new. Refunds the store made
        itself (cancel, return) are already counted — those paths hold the
        order's row lock until they commit, so the event waits on the lock and
        then finds nothing new. Redeliveries are no-ops for the same reason.
        """
        intent_id = charge.get("payment_intent")
        if not intent_id:
            return
        # Only the intent the order was paid with — stray-payment refunds are
        # for some other intent and must not count against the order.
        order = (
            Order.objects.select_for_update()
            .filter(payment_intent_id=intent_id, paid_at__isnull=False)
            .first()
        )
        if order is None:
            return
        stripe_total = gateway.from_cents(charge.get("amount_refunded") or 0)
        new = stripe_total - order.refunded_total
        if new <= 0:
            return
        order.refunded_total = stripe_total
        update_fields = ["refunded_total", "updated_at"]
        if order.status != Order.Status.CANCELLED:
            if stripe_total >= order.total:
                order.status = Order.Status.REFUNDED
                update_fields.append("status")
            elif order.status == Order.Status.DELIVERED:
                # Same status a partial return leaves; paid/shipped orders keep
                # theirs so fulfilment can still go ahead.
                order.status = Order.Status.PARTIALLY_REFUNDED
                update_fields.append("status")
        order.save(update_fields=update_fields)
        to_status = order.status if "status" in update_fields else ""
        transitions.log_event(order, None, f"Refunded ${new} in Stripe", to_status)

        from notifications.models import Notification
        from notifications.service import notify_order
        transaction.on_commit(lambda: notify_order(order, Notification.Kind.ORDER_REFUNDED))

    def _log_dispute(self, event_type, dispute):
        """Put chargebacks on the order's timeline so staff see them. A lost
        dispute isn't a refund (Stripe withdraws the funds separately), so
        ``refunded_total`` is left alone."""
        intent_id = dispute.get("payment_intent")
        if not intent_id:
            return
        order = Order.objects.filter(payment_intent_id=intent_id).first()
        if order is None:
            return
        amount = gateway.from_cents(dispute.get("amount") or 0)
        if event_type == "charge.dispute.created":
            reason = (dispute.get("reason") or "unspecified").replace("_", " ")
            message = f"Payment disputed: ${amount} ({reason}) [{dispute.get('id')}]"
        else:
            message = f"Dispute {dispute.get('status')}: ${amount} [{dispute.get('id')}]"
        # The dispute id in the message makes a redelivered event a no-op.
        if not order.events.filter(message=message).exists():
            transitions.log_event(order, None, message)


class PaymentMethodsView(APIView):
    """The signed-in user's saved cards. ``enabled`` is false without Stripe
    keys (mock mode keeps no cards), so the page can say so instead of erroring."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not gateway.is_live():
            return Response({"enabled": False, "publishable_key": "", "cards": []})
        return Response({
            "enabled": True,
            "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
            "cards": gateway.list_cards(request.user),
        })


class SetupIntentView(APIView):
    """Start saving a card: a SetupIntent the browser confirms with Stripe.js."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            client_secret = gateway.create_setup_intent(request.user)
        except gateway.PaymentsUnavailable as exc:
            return Response({"detail": str(exc)}, status=503)
        return Response({
            "client_secret": client_secret,
            "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        })


class PaymentMethodDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, payment_method_id):
        try:
            gateway.detach_card(request.user, payment_method_id)
        except gateway.PaymentsUnavailable as exc:
            return Response({"detail": str(exc)}, status=503)
        except gateway.PaymentMethodNotFound:
            return Response({"detail": "Card not found."}, status=404)
        return Response(status=204)
