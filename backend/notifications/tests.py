from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from core.asgi import application
from notifications import dispatch, push
from notifications.models import Notification, PushSubscription
from notifications.service import notify
from orders import transitions
from orders.models import Order
from products.models import Category, Product

User = get_user_model()

VAPID = dict(VAPID_PUBLIC_KEY="pub", VAPID_PRIVATE_KEY="priv", VAPID_ADMIN_EMAIL="a@b.co")


def _order(user, **kwargs):
    return Order.objects.create(
        user=user, shipping_address="123 Test St", total=Decimal("80.00"), **kwargs
    )


class NotifyServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="pw-123456"
        )

    def test_notify_creates_row_and_sends_email(self):
        notify(self.user, Notification.Kind.ORDER_PAID, "Order #1 confirmed", "Thanks!")
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Order #1 confirmed")
        self.assertEqual(mail.outbox[0].to, ["buyer@example.com"])

    def test_notify_routes_delivery_through_dispatch(self):
        with patch("notifications.service.dispatch.run") as run:
            notify(self.user, Notification.Kind.ORDER_PAID, "t", "b")
        run.assert_called_once()

    def test_refund_copy_distinguishes_partial(self):
        import types
        from notifications.service import _order_message
        o = types.SimpleNamespace(id=1, status="partially_refunded", refunded_total=Decimal("10.00"))
        _, body = _order_message(o, Notification.Kind.ORDER_REFUNDED)
        self.assertIn("partial refund", body)
        o.status = "refunded"
        _, body = _order_message(o, Notification.Kind.ORDER_REFUNDED)
        self.assertNotIn("partial", body)

    def test_email_includes_order_link(self):
        order = _order(self.user)
        notify(self.user, Notification.Kind.ORDER_PAID, "Order confirmed", "body", order=order)
        self.assertIn(f"/orders/{order.id}", mail.outbox[0].body)

    def test_push_skipped_when_disabled(self):
        with patch.object(push, "send") as send:
            notify(self.user, Notification.Kind.ORDER_PAID, "t", "b")
        send.assert_not_called()

    @override_settings(**VAPID)
    def test_push_sent_to_each_subscription_when_enabled(self):
        PushSubscription.objects.create(
            user=self.user, endpoint="https://push.example/a", p256dh="k", auth="x"
        )
        PushSubscription.objects.create(
            user=self.user, endpoint="https://push.example/b", p256dh="k", auth="x"
        )
        with patch.object(push, "send", return_value=True) as send:
            notify(self.user, Notification.Kind.ORDER_SHIPPED, "shipped", "on its way")
        self.assertEqual(send.call_count, 2)


class DispatchTests(TestCase):
    def test_run_is_synchronous_by_default(self):
        box = []
        self.assertIsNone(dispatch.run(box.append, 1))
        self.assertEqual(box, [1])

    @override_settings(NOTIFICATIONS_ASYNC=True)
    def test_run_executes_task_in_background_when_async(self):
        box = []
        future = dispatch.run(box.append, 1)
        future.result(timeout=5)  # a real Future — the pool ran it off-thread
        self.assertEqual(box, [1])


class OrderEventNotificationTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.p = Product.objects.create(
            name="Widget", price=Decimal("40.00"), stock=10, category=self.cat
        )
        self.user = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="pw-123456"
        )
        self.staff = User.objects.create_user(
            username="staff", email="staff@example.com", password="pw-123456", is_staff=True
        )
        self.client.force_authenticate(self.user)

    def _make_order(self):
        body = {"shipping_address": "123 Test St", "items": [{"product": self.p.id, "quantity": 1}]}
        res = self.client.post("/api/orders/", body, format="json")
        self.assertEqual(res.status_code, 201)
        return Order.objects.get(id=res.data["id"])

    def test_pay_creates_paid_notification(self):
        order = self._make_order()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/api/orders/{order.id}/pay/")
        note = Notification.objects.get(user=self.user, kind=Notification.Kind.ORDER_PAID)
        self.assertEqual(note.order_id, order.id)
        self.assertFalse(note.is_read)

    def test_ship_notification_includes_tracking(self):
        order = self._make_order()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/api/orders/{order.id}/pay/")
        self.client.force_authenticate(self.staff)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                f"/api/orders/{order.id}/ship/",
                {"tracking_carrier": "UPS", "tracking_number": "1Z9"},
                format="json",
            )
        note = Notification.objects.get(user=self.user, kind=Notification.Kind.ORDER_SHIPPED)
        self.assertIn("1Z9", note.body)

    def test_cancel_creates_cancelled_notification(self):
        order = self._make_order()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/api/orders/{order.id}/cancel/")
        self.assertTrue(
            Notification.objects.filter(
                user=self.user, kind=Notification.Kind.ORDER_CANCELLED
            ).exists()
        )


class NotificationApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="pw-123456"
        )
        self.other = User.objects.create_user(
            username="other", email="other@example.com", password="pw-123456"
        )
        self.client.force_authenticate(self.user)
        self.n1 = Notification.objects.create(
            user=self.user, kind=Notification.Kind.ORDER_PAID, title="A"
        )
        self.n2 = Notification.objects.create(
            user=self.user, kind=Notification.Kind.ORDER_SHIPPED, title="B"
        )
        Notification.objects.create(
            user=self.other, kind=Notification.Kind.ORDER_PAID, title="C"
        )

    def test_list_only_own_notifications(self):
        res = self.client.get("/api/notifications/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 2)

    def test_unread_count(self):
        res = self.client.get("/api/notifications/unread_count/")
        self.assertEqual(res.data["unread"], 2)

    def test_mark_one_read(self):
        self.client.post(f"/api/notifications/{self.n1.id}/read/")
        self.n1.refresh_from_db()
        self.assertTrue(self.n1.is_read)
        res = self.client.get("/api/notifications/unread_count/")
        self.assertEqual(res.data["unread"], 1)

    def test_mark_all_read(self):
        res = self.client.post("/api/notifications/read-all/")
        self.assertEqual(res.data["marked_read"], 2)
        self.assertEqual(
            Notification.objects.filter(user=self.user, is_read=False).count(), 0
        )

    def test_cannot_mark_others_notification(self):
        other_note = Notification.objects.get(user=self.other)
        res = self.client.post(f"/api/notifications/{other_note.id}/read/")
        self.assertEqual(res.status_code, 404)


class PushApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="pw-123456"
        )
        self.client.force_authenticate(self.user)

    def test_config_reports_disabled_by_default(self):
        res = self.client.get("/api/push/config/")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["enabled"])

    @override_settings(**VAPID)
    def test_config_reports_enabled_with_keys(self):
        res = self.client.get("/api/push/config/")
        self.assertTrue(res.data["enabled"])
        self.assertEqual(res.data["public_key"], "pub")

    def test_subscribe_rejects_non_object_payload(self):
        res = self.client.post("/api/push/subscribe/", [1, 2, 3], format="json")
        self.assertEqual(res.status_code, 400)

    def test_subscribe_rejects_non_object_keys(self):
        payload = {"endpoint": "https://push.example/z", "keys": "oops"}
        res = self.client.post("/api/push/subscribe/", payload, format="json")
        self.assertEqual(res.status_code, 400)

    def test_subscribe_stores_browser_subscription_shape(self):
        payload = {
            "endpoint": "https://push.example/xyz",
            "keys": {"p256dh": "key123", "auth": "auth123"},
        }
        res = self.client.post("/api/push/subscribe/", payload, format="json")
        self.assertEqual(res.status_code, 201)
        sub = PushSubscription.objects.get(endpoint="https://push.example/xyz")
        self.assertEqual(sub.user, self.user)
        self.assertEqual(sub.p256dh, "key123")

    def test_resubscribe_updates_in_place(self):
        PushSubscription.objects.create(
            user=self.user, endpoint="https://push.example/xyz", p256dh="old", auth="old"
        )
        payload = {
            "endpoint": "https://push.example/xyz",
            "keys": {"p256dh": "new", "auth": "new"},
        }
        res = self.client.post("/api/push/subscribe/", payload, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(PushSubscription.objects.count(), 1)
        sub = PushSubscription.objects.get()
        self.assertEqual(sub.p256dh, "new")

    def test_unsubscribe_removes_subscription(self):
        PushSubscription.objects.create(
            user=self.user, endpoint="https://push.example/xyz", p256dh="k", auth="a"
        )
        res = self.client.delete(
            "/api/push/subscribe/",
            {"endpoint": "https://push.example/xyz"},
            format="json",
        )
        self.assertEqual(res.status_code, 204)
        self.assertEqual(PushSubscription.objects.count(), 0)


class WebSocketPushTests(TransactionTestCase):
    """The /ws/notifications/ socket: token auth, live push, group isolation.

    TransactionTestCase, not TestCase: the socket handshake hits the DB from
    the middleware's database_sync_to_async path, which needs a real
    connection, not TestCase's per-test transaction.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="pw-123456"
        )
        self.other = User.objects.create_user(
            username="other", email="other@example.com", password="pw-123456"
        )

    def _comm(self, user):
        token = str(AccessToken.for_user(user))
        # The communicator parses the query out of the path into scope["query_string"].
        return WebsocketCommunicator(application, f"/ws/notifications/?token={token}")

    async def test_connects_with_valid_token_and_receives_broadcast(self):
        comm = self._comm(self.user)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await sync_to_async(notify)(
            self.user, Notification.Kind.ORDER_PAID, "Order #1 confirmed", "Thanks!"
        )
        msg = await comm.receive_json_from()
        self.assertEqual(msg["type"], "notification")
        self.assertEqual(msg["notification"]["kind"], "order_paid")
        self.assertEqual(msg["notification"]["title"], "Order #1 confirmed")
        self.assertEqual(msg["unread_count"], 1)
        await comm.disconnect()

    async def test_missing_token_rejected(self):
        comm = WebsocketCommunicator(application, "/ws/notifications/")
        connected, code = await comm.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4001)

    async def test_garbage_token_rejected(self):
        comm = WebsocketCommunicator(application, "/ws/notifications/?token=not-a-jwt")
        connected, code = await comm.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4001)

    async def test_expired_token_rejected(self):
        token = AccessToken.for_user(self.user)
        token.set_exp(from_time=timezone.now() - timedelta(hours=3), lifetime=timedelta(hours=1))
        comm = WebsocketCommunicator(application, f"/ws/notifications/?token={token}")
        connected, code = await comm.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4001)

    def _ship_order(self):
        """Sync helper: two real transactions — on_commit fires naturally here."""
        order = _order(self.user)
        transitions.mark_paid(order)
        transitions.ship(order, tracking_number="1Z")
        return order.id

    async def test_transition_pushes_notification_after_commit(self):
        comm = self._comm(self.user)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        order_id = await sync_to_async(self._ship_order)()
        first = await comm.receive_json_from()
        second = await comm.receive_json_from()
        self.assertEqual(
            [m["notification"]["kind"] for m in (first, second)],
            ["order_paid", "order_shipped"],
        )
        self.assertEqual(second["notification"]["order"], order_id)
        self.assertEqual(second["unread_count"], 2)
        await comm.disconnect()

    async def test_other_users_socket_receives_nothing(self):
        comm = self._comm(self.other)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await sync_to_async(notify)(self.user, Notification.Kind.ORDER_PAID, "private", "body")
        self.assertTrue(await comm.receive_nothing(timeout=0.2))
        await comm.disconnect()
