import asyncio
import json

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TransactionTestCase
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken
from unittest.mock import patch

from chat.models import ChatMessage, ChatThread
from chat.service import broadcast_message
from chat.throttling import ChatSendThrottle
from core.asgi import application

User = get_user_model()


class ChatApiTests(APITestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="pw-123456"
        )
        self.other = User.objects.create_user(
            username="other", email="other@example.com", password="pw-123456"
        )
        self.staff = User.objects.create_user(
            username="staff", email="staff@example.com", password="pw-123456", is_staff=True
        )
        self.client.force_authenticate(self.buyer)

    def _post(self, body, **extra):
        return self.client.post("/api/chat/messages/", {"body": body, **extra}, format="json")

    def test_thread_get_or_create_is_idempotent(self):
        first = self.client.get("/api/chat/thread/")
        second = self.client.get("/api/chat/thread/")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(ChatThread.objects.count(), 1)

    def test_customer_message_creates_thread_and_message(self):
        res = self._post("Hi, where is my order?")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["thread_user_id"], self.buyer.id)
        self.assertEqual(res.data["sender"], self.buyer.id)
        self.assertIsNone(res.data["read_at"])
        self.assertTrue(ChatThread.objects.filter(user=self.buyer).exists())
        self.assertEqual(ChatMessage.objects.filter(thread__user=self.buyer).count(), 1)

    def test_history_is_forced_to_own_thread(self):
        self._post_as(self.other, "someone else's problem")
        res = self.client.get(f"/api/chat/messages/?thread={self.other.id}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(all(m["thread_user_id"] == self.buyer.id for m in res.data["results"]))

    def _post_as(self, user, body, **extra):
        self.client.force_authenticate(user)
        res = self._post(body, **extra)
        self.client.force_authenticate(self.buyer)
        return res

    def test_staff_inbox_lists_threads_with_unread_and_preview(self):
        self._post("first")
        self._post("second — the preview")
        self.client.force_authenticate(self.staff)
        res = self.client.get("/api/chat/threads/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        row = res.data[0]
        self.assertEqual(row["username"], "buyer")
        self.assertEqual(row["unread"], 2)
        self.assertEqual(row["last_message_body"], "second — the preview")

    def test_customer_cannot_list_staff_inbox(self):
        res = self.client.get("/api/chat/threads/")
        self.assertEqual(res.status_code, 403)

    def test_staff_reply_sets_buyer_unread(self):
        self.client.get("/api/chat/thread/")  # the buyer's thread must exist first
        res = self._post_as(self.staff, "hello from support", thread=self.buyer.id)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["sender"], self.staff.id)
        thread = self.client.get("/api/chat/thread/").data
        self.assertEqual(thread["unread"], 1)

    def test_staff_history_requires_thread_param(self):
        self.client.force_authenticate(self.staff)
        res = self.client.get("/api/chat/messages/")
        self.assertEqual(res.status_code, 400)

    def test_body_is_validated(self):
        self.assertEqual(self._post("x" * 2001).status_code, 400)
        self.assertEqual(self._post("").status_code, 400)

    def test_anonymous_is_unauthorized(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/api/chat/thread/").status_code, 401)


class ChatThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()  # throttle history lives in the cache — not rolled back
        self.user = User.objects.create_user(
            username="chatty", email="chatty@example.com", password="pw-123456"
        )
        self.client.force_authenticate(self.user)

    @patch.dict(ChatSendThrottle.THROTTLE_RATES, {"chat-send": "2/min"})
    def test_sending_is_throttled_but_reading_is_not(self):
        for _ in range(2):
            res = self.client.post("/api/chat/messages/", {"body": "x"}, format="json")
            self.assertEqual(res.status_code, 201)
        self.assertEqual(
            self.client.post("/api/chat/messages/", {"body": "x"}, format="json").status_code,
            429,
        )
        self.assertEqual(self.client.get("/api/chat/messages/").status_code, 200)


class ChatSocketTests(TransactionTestCase):
    """The /ws/chat/ socket: auth, isolation, and the typing/read/presence relays.

    TransactionTestCase, not TestCase — the handshake hits the DB via
    database_sync_to_async (see notifications.tests for the full story).
    Staff may receive events twice (thread group + staff feed); the FE dedupes
    message ids and treats the rest as idempotent, so tests use receive-until.
    """

    def setUp(self):
        self.buyer = User.objects.create_user(
            username="ws_buyer", email="ws_buyer@example.com", password="pw-123456"
        )
        self.other = User.objects.create_user(
            username="ws_other", email="ws_other@example.com", password="pw-123456"
        )
        self.staff = User.objects.create_user(
            username="ws_staff", email="ws_staff@example.com", password="pw-123456", is_staff=True
        )

    def _comm(self, user):
        token = str(AccessToken.for_user(user))
        return WebsocketCommunicator(application, f"/ws/chat/?token={token}")

    async def _thread(self, user):
        return await sync_to_async(ChatThread.objects.create)(user=user)

    async def _msg(self, thread, sender, body):
        return await sync_to_async(ChatMessage.objects.create)(
            thread=thread, sender=sender, body=body
        )

    async def _recv_until(self, comm, pred, tries=6, timeout=0.5):
        seen = []
        for _ in range(tries):
            try:
                event = await comm.receive_json_from(timeout=timeout)
            except asyncio.TimeoutError:
                continue
            seen.append(event)
            if pred(event):
                return event
        raise AssertionError(f"expected event never arrived; saw: {seen}")

    async def test_unauthenticated_rejected(self):
        comm = WebsocketCommunicator(application, "/ws/chat/")
        connected, code = await comm.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4001)

    async def test_buyer_receives_staff_reply_live(self):
        thread = await self._thread(self.buyer)
        comm = self._comm(self.buyer)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        msg = await self._msg(thread, self.staff, "hello from support")
        await sync_to_async(broadcast_message)(msg)
        event = await self._recv_until(comm, lambda e: e["type"] == "chat.message")
        self.assertEqual(event["message"]["body"], "hello from support")
        self.assertEqual(event["message"]["thread_user_id"], self.buyer.id)
        await comm.disconnect()

    async def test_staff_watch_receives_buyer_message(self):
        thread = await self._thread(self.buyer)
        comm = self._comm(self.staff)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await comm.send_to(
            text_data=json.dumps({"type": "chat.watch", "thread_user_id": self.buyer.id})
        )
        msg = await self._msg(thread, self.buyer, "I need help")
        await sync_to_async(broadcast_message)(msg)
        event = await self._recv_until(
            comm, lambda e: e["type"] == "chat.message" and e["message"]["sender"] == self.buyer.id
        )
        self.assertEqual(event["message"]["body"], "I need help")
        await comm.disconnect()

    async def test_non_staff_watch_is_ignored(self):
        await self._thread(self.other)
        comm = self._comm(self.buyer)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await comm.send_to(
            text_data=json.dumps({"type": "chat.watch", "thread_user_id": self.other.id})
        )
        # a working watch would have broadcast the watcher's presence
        self.assertTrue(await comm.receive_nothing(timeout=0.2))
        await comm.disconnect()

    async def test_thread_isolation(self):
        other_thread = await self._thread(self.other)
        comm = self._comm(self.buyer)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        msg = await self._msg(other_thread, self.other, "private")
        await sync_to_async(broadcast_message)(msg)
        self.assertTrue(await comm.receive_nothing(timeout=0.2))
        await comm.disconnect()

    async def test_malformed_frame_keeps_socket_alive(self):
        thread = await self._thread(self.buyer)
        comm = self._comm(self.buyer)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await comm.send_to(text_data="not json at all")
        msg = await self._msg(thread, self.staff, "still there?")
        await sync_to_async(broadcast_message)(msg)
        event = await self._recv_until(comm, lambda e: e["type"] == "chat.message")
        self.assertEqual(event["message"]["body"], "still there?")
        await comm.disconnect()

    async def test_typing_relays_between_parties(self):
        await self._thread(self.buyer)
        staff_comm = self._comm(self.staff)
        connected, _ = await staff_comm.connect()
        self.assertTrue(connected)
        buyer_comm = self._comm(self.buyer)
        connected, _ = await buyer_comm.connect()
        self.assertTrue(connected)
        await buyer_comm.send_to(text_data=json.dumps({"type": "chat.typing"}))
        event = await self._recv_until(staff_comm, lambda e: e["type"] == "chat.typing")
        self.assertEqual(event["user_id"], self.buyer.id)
        await buyer_comm.disconnect()
        await staff_comm.disconnect()

    async def test_read_receipt_persists_and_broadcasts(self):
        thread = await self._thread(self.buyer)
        msg = await self._msg(thread, self.staff, "support here")
        comm = self._comm(self.buyer)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await comm.send_to(text_data=json.dumps({"type": "chat.read"}))
        event = await self._recv_until(comm, lambda e: e["type"] == "chat.read")
        self.assertEqual(event["reader_id"], self.buyer.id)
        reloaded = await sync_to_async(ChatMessage.objects.get)(pk=msg.pk)
        self.assertIsNotNone(reloaded.read_at)
        await comm.disconnect()

    async def test_presence_flows_both_ways(self):
        await self._thread(self.buyer)
        staff_comm = self._comm(self.staff)
        connected, _ = await staff_comm.connect()
        self.assertTrue(connected)
        await staff_comm.send_to(
            text_data=json.dumps({"type": "chat.watch", "thread_user_id": self.buyer.id})
        )
        buyer_comm = self._comm(self.buyer)
        connected, _ = await buyer_comm.connect()
        self.assertTrue(connected)
        # buyer's connect presence reaches the watching staff (staff feed)
        event = await self._recv_until(
            staff_comm,
            lambda e: e["type"] == "chat.presence" and e["user_id"] == self.buyer.id,
        )
        self.assertTrue(event["online"])
        # staff's watch presence reaches the buyer (thread group)
        event = await self._recv_until(
            buyer_comm,
            lambda e: e["type"] == "chat.presence" and e["user_id"] == self.staff.id,
        )
        self.assertTrue(event["online"])
        # Generous timeout: disconnect() waits for the consumer to finish, and
        # on a loaded runner the default 1s wait_for can cancel the app task
        # mid-broadcast, losing the offline event.
        await buyer_comm.disconnect(timeout=5)
        event = await self._recv_until(
            staff_comm,
            lambda e: e["type"] == "chat.presence"
            and e["user_id"] == self.buyer.id
            and not e["online"],
        )
        await staff_comm.disconnect(timeout=5)
