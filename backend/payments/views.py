from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from orders import transitions
from orders.models import Order

from . import gateway


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """Authoritative payment confirmation for live Stripe — moves the matching
    order to PAID on ``payment_intent.succeeded``. Verified and idempotent.
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

        if event["type"] == "payment_intent.succeeded":
            intent = event["data"]["object"]
            order_id = (intent.get("metadata") or {}).get("order_id")
            self._mark_paid(intent.get("id"), order_id, intent.get("amount"))

        return HttpResponse(status=200)

    def _mark_paid(self, intent_id, order_id, amount=None):
        order = None
        if order_id:
            order = Order.objects.filter(pk=order_id).first()
        if order is None and intent_id:
            order = Order.objects.filter(payment_intent_id=intent_id).first()
        if order is None or order.status != Order.Status.PENDING:
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
