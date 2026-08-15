import json
import types
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from orders.models import Order
from payments import gateway
from products.models import Category, Product

User = get_user_model()

LIVE = dict(
    STRIPE_SECRET_KEY="sk_test_x",
    STRIPE_PUBLISHABLE_KEY="pk_test_x",
    STRIPE_WEBHOOK_SECRET="whsec_x",
)


def _fake_stripe(intent_id="pi_live_1", secret="pi_live_1_secret", status="succeeded", amount=0):
    s = MagicMock()
    s.PaymentIntent.create.return_value = types.SimpleNamespace(id=intent_id, client_secret=secret)
    s.PaymentIntent.retrieve.return_value = types.SimpleNamespace(
        id=intent_id, status=status, amount=amount
    )
    s.Refund.create.return_value = types.SimpleNamespace(id="re_live_1")
    return s


class GatewayUnitTests(TestCase):
    def test_to_cents_rounds_to_minor_units(self):
        self.assertEqual(gateway.to_cents(Decimal("40.00")), 4000)
        self.assertEqual(gateway.to_cents(Decimal("19.99")), 1999)

    def test_mock_mode_is_not_live_by_default(self):
        self.assertFalse(gateway.is_live())

    def test_create_refund_noop_for_non_positive(self):
        order = types.SimpleNamespace(pk=1, payment_intent_id="")
        self.assertEqual(gateway.create_refund(order, Decimal("0")), "")


class FreeOrderPaymentTests(TestCase):
    """A $0 order must settle without a Stripe intent even in live mode."""

    @override_settings(**LIVE)
    def test_zero_total_uses_mock_intent_even_when_live(self):
        order = types.SimpleNamespace(pk=7, total=Decimal("0.00"), payment_intent_id="")
        _secret, intent_id, mock = gateway.create_payment_intent(order)
        self.assertTrue(mock)
        self.assertTrue(intent_id.startswith(gateway.MOCK_INTENT_PREFIX))

    @override_settings(**LIVE)
    def test_zero_total_verifies_as_paid(self):
        order = types.SimpleNamespace(pk=7, total=Decimal("0.00"), payment_intent_id="")
        ok, _detail = gateway.verify_paid(order)
        self.assertTrue(ok)

    def test_create_refund_mock_id_without_keys(self):
        order = types.SimpleNamespace(pk=7, payment_intent_id="mock_pi_7")
        self.assertEqual(gateway.create_refund(order, Decimal("5")), "mock_re_7")

    @override_settings(**LIVE)
    def test_create_refund_calls_stripe_when_live(self):
        order = types.SimpleNamespace(pk=9, payment_intent_id="pi_live_1")
        with patch.object(gateway, "_stripe", return_value=_fake_stripe()) as m:
            rid = gateway.create_refund(order, Decimal("12.50"))
        self.assertEqual(rid, "re_live_1")
        m.return_value.Refund.create.assert_called_once_with(
            payment_intent="pi_live_1", amount=1250
        )


class PaymentIntentApiTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.p = Product.objects.create(
            name="Widget", price=Decimal("40.00"), stock=10, category=self.cat
        )
        self.user = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="pw-123456"
        )
        self.client.force_authenticate(self.user)

    def _order(self):
        body = {"shipping_address": "123 Test St", "items": [{"product": self.p.id, "quantity": 2}]}
        res = self.client.post("/api/orders/", body, format="json")
        self.assertEqual(res.status_code, 201)
        return Order.objects.get(id=res.data["id"])

    def test_mock_intent_returns_stub_and_stores_id(self):
        order = self._order()
        res = self.client.post(f"/api/orders/{order.id}/create-payment-intent/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["mock"])
        self.assertTrue(res.data["client_secret"])
        order.refresh_from_db()
        self.assertEqual(order.payment_intent_id, f"mock_pi_{order.id}")

    def test_intent_rejected_for_non_pending_order(self):
        order = self._order()
        self.client.post(f"/api/orders/{order.id}/pay/")  # -> PAID
        res = self.client.post(f"/api/orders/{order.id}/create-payment-intent/")
        self.assertEqual(res.status_code, 400)

    def test_mock_pay_marks_order_paid(self):
        order = self._order()
        res = self.client.post(f"/api/orders/{order.id}/pay/")
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    @override_settings(**LIVE)
    def test_live_intent_uses_stripe_and_exposes_publishable_key(self):
        order = self._order()
        with patch.object(gateway, "_stripe", return_value=_fake_stripe()):
            res = self.client.post(f"/api/orders/{order.id}/create-payment-intent/")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["mock"])
        self.assertEqual(res.data["publishable_key"], "pk_test_x")
        order.refresh_from_db()
        self.assertEqual(order.payment_intent_id, "pi_live_1")

    @override_settings(**LIVE)
    def test_reuses_existing_open_intent(self):
        order = self._order()
        order.payment_intent_id = "pi_live_existing"
        order.save(update_fields=["payment_intent_id"])
        reusable = types.SimpleNamespace(
            id="pi_live_existing",
            client_secret="sec_existing",
            status="requires_payment_method",
            amount=gateway.to_cents(order.total),
        )
        fake = MagicMock()
        fake.PaymentIntent.retrieve.return_value = reusable
        with patch.object(gateway, "_stripe", return_value=fake):
            res = self.client.post(f"/api/orders/{order.id}/create-payment-intent/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["client_secret"], "sec_existing")
        fake.PaymentIntent.create.assert_not_called()
        order.refresh_from_db()
        self.assertEqual(order.payment_intent_id, "pi_live_existing")

    @override_settings(**LIVE)
    def test_live_pay_rejected_when_intent_not_succeeded(self):
        order = self._order()
        order.payment_intent_id = "pi_live_1"
        order.save(update_fields=["payment_intent_id"])
        with patch.object(gateway, "_stripe", return_value=_fake_stripe(status="requires_payment_method")):
            res = self.client.post(f"/api/orders/{order.id}/pay/")
        self.assertEqual(res.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    @override_settings(**LIVE)
    def test_live_pay_succeeds_when_intent_succeeded(self):
        order = self._order()
        order.payment_intent_id = "pi_live_1"
        order.save(update_fields=["payment_intent_id"])
        fake = _fake_stripe(status="succeeded", amount=gateway.to_cents(order.total))
        with patch.object(gateway, "_stripe", return_value=fake):
            res = self.client.post(f"/api/orders/{order.id}/pay/")
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    @override_settings(**LIVE)
    def test_live_pay_rejected_when_intent_amount_mismatches(self):
        order = self._order()
        order.payment_intent_id = "pi_live_1"
        order.save(update_fields=["payment_intent_id"])
        # Succeeded, but for one cent less than the order total.
        fake = _fake_stripe(status="succeeded", amount=gateway.to_cents(order.total) - 1)
        with patch.object(gateway, "_stripe", return_value=fake):
            res = self.client.post(f"/api/orders/{order.id}/pay/")
        self.assertEqual(res.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)


class WebhookTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.p = Product.objects.create(
            name="Widget", price=Decimal("40.00"), stock=10, category=self.cat
        )
        self.user = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="pw-123456"
        )

    def _pending_order(self):
        order = Order.objects.create(
            user=self.user, shipping_address="123 Test St", total=Decimal("80.00")
        )
        return order

    def _post(self, body=b"{}"):
        return self.client.post(
            "/api/payments/webhook/", data=body, content_type="application/json"
        )

    def test_payment_succeeded_marks_order_paid(self):
        order = self._pending_order()
        event = {
            "type": "payment_intent.succeeded",
            "data": {"object": {
                "id": "pi_x",
                "amount": gateway.to_cents(order.total),
                "metadata": {"order_id": str(order.id)},
            }},
        }
        with patch.object(gateway, "construct_event", return_value=event):
            res = self._post()
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    def test_amount_mismatch_does_not_mark_paid(self):
        order = self._pending_order()
        event = {
            "type": "payment_intent.succeeded",
            "data": {"object": {
                "id": "pi_x",
                "amount": gateway.to_cents(order.total) - 100,  # underpaid
                "metadata": {"order_id": str(order.id)},
            }},
        }
        with patch.object(gateway, "construct_event", return_value=event):
            res = self._post()
        self.assertEqual(res.status_code, 200)  # ack the event, but do not confirm
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_resolves_order_by_intent_id_when_metadata_missing(self):
        order = self._pending_order()
        order.payment_intent_id = "pi_match"
        order.save(update_fields=["payment_intent_id"])
        event = {
            "type": "payment_intent.succeeded",
            "data": {"object": {
                "id": "pi_match", "amount": gateway.to_cents(order.total), "metadata": {},
            }},
        }
        with patch.object(gateway, "construct_event", return_value=event):
            self._post()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    def test_invalid_signature_returns_400(self):
        with patch.object(gateway, "construct_event", side_effect=ValueError("bad sig")):
            res = self._post()
        self.assertEqual(res.status_code, 400)

    def test_unhandled_event_type_is_ignored(self):
        order = self._pending_order()
        event = {"type": "charge.refunded", "data": {"object": {}}}
        with patch.object(gateway, "construct_event", return_value=event):
            res = self._post()
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
