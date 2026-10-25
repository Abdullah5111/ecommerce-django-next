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

    @override_settings(STRIPE_CURRENCY="jpy")
    def test_to_cents_uses_whole_units_for_zero_decimal_currency(self):
        # ¥8000 must bill as 8000, not 800000.
        self.assertEqual(gateway.to_cents(Decimal("8000.00")), 8000)

    def test_mock_mode_is_not_live_by_default(self):
        self.assertFalse(gateway.is_live())

    def test_create_refund_noop_for_non_positive(self):
        order = types.SimpleNamespace(pk=1, payment_intent_id="")
        self.assertEqual(gateway.create_refund(order, Decimal("0"), idempotency_key="k"), "")


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
        self.assertEqual(gateway.create_refund(order, Decimal("5"), idempotency_key="k"), "mock_re_7")

    @override_settings(**LIVE)
    def test_create_refund_calls_stripe_when_live(self):
        order = types.SimpleNamespace(pk=9, payment_intent_id="pi_live_1")
        with patch.object(gateway, "_stripe", return_value=_fake_stripe()) as m:
            rid = gateway.create_refund(order, Decimal("12.50"), idempotency_key="cancel-9")
        self.assertEqual(rid, "re_live_1")
        m.return_value.Refund.create.assert_called_once_with(
            payment_intent="pi_live_1", amount=1250, idempotency_key="cancel-9"
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

    def test_stores_intent_id_when_resolved_by_metadata(self):
        order = self._pending_order()  # no payment_intent_id yet
        event = {
            "type": "payment_intent.succeeded",
            "data": {"object": {
                "id": "pi_hosted",
                "amount": gateway.to_cents(order.total),
                "metadata": {"order_id": str(order.id)},
            }},
        }
        with patch.object(gateway, "construct_event", return_value=event):
            self._post()
        order.refresh_from_db()
        # Stored so a later refund can reach the real Stripe intent.
        self.assertEqual(order.payment_intent_id, "pi_hosted")

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
        event = {"type": "customer.created", "data": {"object": {}}}
        with patch.object(gateway, "construct_event", return_value=event):
            res = self._post()
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)


@override_settings(PAYMENTS_MOCK=False, STRIPE_SECRET_KEY="")
class MockIsolationTests(APITestCase):
    """No Stripe key and mock not enabled (a misconfigured production deploy):
    payment must be refused, never faked."""

    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.p = Product.objects.create(
            name="Widget", price=Decimal("40.00"), stock=10, category=self.cat
        )
        self.user = User.objects.create_user(
            username="isolated", email="isolated@example.com", password="pw-123456"
        )
        self.client.force_authenticate(self.user)

    def _order(self):
        body = {"shipping_address": "123 Test St", "items": [{"product": self.p.id, "quantity": 1}]}
        res = self.client.post("/api/orders/", body, format="json")
        self.assertEqual(res.status_code, 201)
        return Order.objects.get(id=res.data["id"])

    def test_pay_is_refused_and_order_stays_pending(self):
        order = self._order()
        res = self.client.post(f"/api/orders/{order.id}/pay/")
        self.assertEqual(res.status_code, 503)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_payment_intent_is_refused(self):
        order = self._order()
        res = self.client.post(f"/api/orders/{order.id}/create-payment-intent/")
        self.assertEqual(res.status_code, 503)

    def test_zero_total_order_still_settles(self):
        """Nothing to charge (e.g. a 100%-off coupon) — no payment provider needed."""
        order = self._order()
        Order.objects.filter(pk=order.pk).update(total=Decimal("0.00"))
        res = self.client.post(f"/api/orders/{order.id}/pay/")
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)


@override_settings(**LIVE)
class StrayPaymentTests(APITestCase):
    """A succeeded intent that didn't pay the order must be refunded."""

    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.p = Product.objects.create(
            name="Widget", price=Decimal("40.00"), stock=10, category=self.cat
        )
        self.user = User.objects.create_user(
            username="stray", email="stray@example.com", password="pw-123456"
        )

    def _order(self, **kwargs):
        return Order.objects.create(
            user=self.user, shipping_address="123 Test St", total=Decimal("80.00"), **kwargs
        )

    def _succeeded(self, order, intent_id):
        event = {
            "type": "payment_intent.succeeded",
            "data": {"object": {
                "id": intent_id,
                "amount": gateway.to_cents(order.total),
                "metadata": {"order_id": str(order.id)},
            }},
        }
        fake = _fake_stripe()
        with patch.object(gateway, "construct_event", return_value=event), \
                patch.object(gateway, "_stripe", return_value=fake):
            res = self.client.post(
                "/api/payments/webhook/", data=b"{}", content_type="application/json"
            )
        self.assertEqual(res.status_code, 200)
        return fake

    def test_payment_for_cancelled_order_is_refunded(self):
        order = self._order(status=Order.Status.CANCELLED, payment_intent_id="pi_late")
        fake = self._succeeded(order, "pi_late")
        fake.Refund.create.assert_called_once_with(
            payment_intent="pi_late", amount=8000, idempotency_key="stray-pi_late"
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    def test_second_intent_on_paid_order_is_refunded(self):
        from django.utils import timezone

        order = self._order(
            status=Order.Status.PAID, paid_at=timezone.now(), payment_intent_id="pi_first"
        )
        fake = self._succeeded(order, "pi_stale_tab")
        fake.Refund.create.assert_called_once_with(
            payment_intent="pi_stale_tab", amount=8000, idempotency_key="stray-pi_stale_tab"
        )

    def test_redelivered_event_for_the_paying_intent_is_a_noop(self):
        from django.utils import timezone

        order = self._order(
            status=Order.Status.PAID, paid_at=timezone.now(), payment_intent_id="pi_paid"
        )
        fake = self._succeeded(order, "pi_paid")
        fake.Refund.create.assert_not_called()

    def test_cancelling_unpaid_order_cancels_its_open_intent(self):
        from orders import transitions

        order = self._order(payment_intent_id="pi_open")
        fake = _fake_stripe()
        with patch.object(gateway, "_stripe", return_value=fake), \
                self.captureOnCommitCallbacks(execute=True):
            transitions.cancel(order)
        fake.PaymentIntent.cancel.assert_called_once_with("pi_open")


@override_settings(**LIVE)
class RefundIdempotencyTests(APITestCase):
    """Every Stripe refund carries a key naming the event it refunds, so a
    retry after a rolled-back transaction can't refund twice."""

    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.p = Product.objects.create(
            name="Widget", price=Decimal("40.00"), stock=10, category=self.cat
        )
        self.user = User.objects.create_user(
            username="idem", email="idem@example.com", password="pw-123456"
        )

    def test_cancelling_paid_order_refunds_with_cancel_key(self):
        from django.utils import timezone

        from orders import transitions

        order = Order.objects.create(
            user=self.user, shipping_address="123 Test St", total=Decimal("80.00"),
            status=Order.Status.PAID, paid_at=timezone.now(), payment_intent_id="pi_live_1",
        )
        fake = _fake_stripe()
        with patch.object(gateway, "_stripe", return_value=fake):
            transitions.cancel(order)
        fake.Refund.create.assert_called_once_with(
            payment_intent="pi_live_1", amount=8000, idempotency_key=f"cancel-{order.pk}"
        )


class DashboardRefundTests(APITestCase):
    """``charge.refunded`` mirrors refunds made outside the store onto the order."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="dash", email="dash@example.com", password="pw-123456"
        )

    def _order(self, **kwargs):
        from django.utils import timezone

        fields = dict(
            user=self.user, shipping_address="123 Test St", total=Decimal("80.00"),
            subtotal=Decimal("80.00"), status=Order.Status.PAID, paid_at=timezone.now(),
            payment_intent_id="pi_paid",
        )
        fields.update(kwargs)
        return Order.objects.create(**fields)

    def _refunded(self, amount_refunded, intent_id="pi_paid"):
        event = {
            "type": "charge.refunded",
            "data": {"object": {
                "id": "ch_1", "payment_intent": intent_id, "amount_refunded": amount_refunded,
            }},
        }
        with patch.object(gateway, "construct_event", return_value=event), \
                self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(
                "/api/payments/webhook/", data=b"{}", content_type="application/json"
            )
        self.assertEqual(res.status_code, 200)

    def test_full_dashboard_refund_marks_order_refunded(self):
        order = self._order()
        self._refunded(8000)
        order.refresh_from_db()
        self.assertEqual(order.refunded_total, Decimal("80.00"))
        self.assertEqual(order.status, Order.Status.REFUNDED)
        self.assertTrue(order.events.filter(message="Refunded $80.00 in Stripe").exists())

    def test_partial_refund_on_paid_order_keeps_it_shippable(self):
        order = self._order()
        self._refunded(1500)
        order.refresh_from_db()
        self.assertEqual(order.refunded_total, Decimal("15.00"))
        self.assertEqual(order.status, Order.Status.PAID)

    def test_partial_refund_on_delivered_order_is_partially_refunded(self):
        order = self._order(status=Order.Status.DELIVERED)
        self._refunded(1500)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PARTIALLY_REFUNDED)

    def test_only_the_new_part_of_a_running_total_is_recorded(self):
        order = self._order(status=Order.Status.DELIVERED)
        self._refunded(1500)
        self._refunded(4000)  # Stripe sends the charge's cumulative total
        order.refresh_from_db()
        self.assertEqual(order.refunded_total, Decimal("40.00"))
        self.assertTrue(order.events.filter(message="Refunded $25.00 in Stripe").exists())

    def test_redelivered_event_is_a_noop(self):
        order = self._order()
        self._refunded(1500)
        self._refunded(1500)
        order.refresh_from_db()
        self.assertEqual(order.refunded_total, Decimal("15.00"))
        self.assertEqual(order.events.filter(message__contains="in Stripe").count(), 1)

    def test_store_issued_refund_is_not_counted_twice(self):
        # A cancel already recorded the full refund; Stripe's event echoes it.
        order = self._order(status=Order.Status.CANCELLED, refunded_total=Decimal("80.00"))
        self._refunded(8000)
        order.refresh_from_db()
        self.assertEqual(order.refunded_total, Decimal("80.00"))
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertFalse(order.events.filter(message__contains="in Stripe").exists())

    def test_refund_of_another_intent_is_ignored(self):
        # A stray-payment refund is for a different intent than the order's.
        order = self._order()
        self._refunded(8000, intent_id="pi_stray")
        order.refresh_from_db()
        self.assertEqual(order.refunded_total, Decimal("0"))
        self.assertEqual(order.status, Order.Status.PAID)

    def test_unpaid_order_is_ignored(self):
        order = self._order(status=Order.Status.PENDING, paid_at=None)
        self._refunded(8000)
        order.refresh_from_db()
        self.assertEqual(order.refunded_total, Decimal("0"))

    def test_customer_is_notified(self):
        from notifications.models import Notification

        self._order()
        self._refunded(8000)
        self.assertTrue(
            Notification.objects.filter(
                user=self.user, kind=Notification.Kind.ORDER_REFUNDED
            ).exists()
        )


class DisputeTests(APITestCase):
    """Chargebacks land on the order's timeline."""

    def setUp(self):
        from django.utils import timezone

        user = User.objects.create_user(
            username="disp", email="disp@example.com", password="pw-123456"
        )
        self.order = Order.objects.create(
            user=user, shipping_address="123 Test St", total=Decimal("80.00"),
            status=Order.Status.DELIVERED, paid_at=timezone.now(), payment_intent_id="pi_paid",
        )

    def _dispute(self, event_type, **fields):
        dispute = {"id": "dp_1", "payment_intent": "pi_paid", "amount": 8000}
        dispute.update(fields)
        event = {"type": event_type, "data": {"object": dispute}}
        with patch.object(gateway, "construct_event", return_value=event):
            res = self.client.post(
                "/api/payments/webhook/", data=b"{}", content_type="application/json"
            )
        self.assertEqual(res.status_code, 200)

    def test_opened_dispute_is_logged_once(self):
        self._dispute("charge.dispute.created", reason="product_not_received")
        self._dispute("charge.dispute.created", reason="product_not_received")
        events = self.order.events.filter(message__startswith="Payment disputed")
        self.assertEqual(events.count(), 1)
        self.assertEqual(
            events.get().message, "Payment disputed: $80.00 (product not received) [dp_1]"
        )

    def test_closed_dispute_logs_outcome_and_leaves_refunds_alone(self):
        self._dispute("charge.dispute.closed", status="lost")
        self.assertTrue(
            self.order.events.filter(message="Dispute lost: $80.00 [dp_1]").exists()
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.refunded_total, Decimal("0"))
        self.assertEqual(self.order.status, Order.Status.DELIVERED)
