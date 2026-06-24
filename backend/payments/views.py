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
    """Authoritative payment confirmation for live Stripe.

    Stripe POSTs ``payment_intent.succeeded`` here once a card is charged; we
    move the matching order to PAID. Signature-verified and idempotent — replays
    are harmless because ``mark_paid`` only fires on a PENDING order.
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
            self._mark_paid(intent.get("id"), order_id)

        return HttpResponse(status=200)

    def _mark_paid(self, intent_id, order_id):
        order = None
        if order_id:
            order = Order.objects.filter(pk=order_id).first()
        if order is None and intent_id:
            order = Order.objects.filter(payment_intent_id=intent_id).first()
        if order is None or order.status != Order.Status.PENDING:
            return
        try:
            transitions.mark_paid(order)
        except transitions.TransitionError:
            pass
