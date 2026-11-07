import json
from unittest import skipUnless
from unittest.mock import patch

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TransactionTestCase
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from chat.models import ChatMessage, ChatThread
from chat.presence import presence
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

    def test_thread_appears_only_after_first_message(self):
        self.assertEqual(self.client.get("/api/chat/thread/").status_code, 404)
        self.assertEqual(ChatThread.objects.count(), 0)
        self.assertEqual(self._post("hi").status_code, 201)
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

    def test_empty_threads_sort_below_active_ones(self):
        idle = User.objects.create_user(
            username="idle", email="idle@example.com", password="pw-123456"
        )
        ChatThread.objects.create(user=idle)  # opened the widget, never messaged
        self._post("active conversation")
        self.client.force_authenticate(self.staff)
        res = self.client.get("/api/chat/threads/")
        self.assertEqual([t["username"] for t in res.data], ["buyer", "idle"])

    def test_staff_reply_sets_buyer_unread(self):
        self._post("opening message")  # the buyer's thread must exist first
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

    def test_deleted_sender_messages_count_as_customer_unread(self):
        self._post("opening message")
        thread = ChatThread.objects.get(user=self.buyer)
        ChatMessage.objects.create(thread=thread, sender=None, body="ghost")  # user deleted
        self.client.force_authenticate(self.staff)
        row = next(
            t for t in self.client.get("/api/chat/threads/").data if t["username"] == "buyer"
        )
        self.assertEqual(row["unread"], 2)

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
    """The /ws/chat/ socket. TransactionTestCase, not TestCase — the handshake
    hits the DB via database_sync_to_async. Staff may receive events twice
    (thread group + staff feed); tests use receive-until."""

    def setUp(self):
        # module-global, like the cache — not rolled back between tests
        presence.clear()
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
            except TimeoutError:
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

    async def _ticket_comm(self, user):
        from accounts import ws_tickets

        ticket = await sync_to_async(ws_tickets.issue)(user)
        return ticket, WebsocketCommunicator(application, f"/ws/chat/?ticket={ticket}")

    async def test_ticket_opens_the_socket(self):
        _, comm = await self._ticket_comm(self.buyer)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await comm.disconnect()

    async def test_a_used_ticket_cannot_open_a_second_socket(self):
        ticket, first = await self._ticket_comm(self.buyer)
        connected, _ = await first.connect()
        self.assertTrue(connected)
        replay = WebsocketCommunicator(application, f"/ws/chat/?ticket={ticket}")
        connected, code = await replay.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4001)
        await first.disconnect()

    async def test_unknown_ticket_is_refused(self):
        comm = WebsocketCommunicator(application, "/ws/chat/?ticket=forged")
        connected, code = await comm.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4001)

    async def test_ticket_of_a_deactivated_user_is_refused(self):
        _, comm = await self._ticket_comm(self.buyer)
        await sync_to_async(User.objects.filter(pk=self.buyer.pk).update)(is_active=False)
        connected, code = await comm.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4001)

    async def test_notifications_arrive_on_the_chat_socket(self):
        # The frontend opens only this socket, so it must carry notification
        # pushes too — sent through the real notify() path.
        from notifications.models import Notification
        from notifications.service import notify

        comm = self._comm(self.buyer)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await sync_to_async(notify)(
            self.buyer, Notification.Kind.ORDER_PAID, "Order #1 confirmed", "Thanks!"
        )
        event = await self._recv_until(comm, lambda e: e["type"] == "notification")
        self.assertEqual(event["notification"]["title"], "Order #1 confirmed")
        self.assertEqual(event["unread_count"], 1)
        await comm.disconnect()

    async def test_notifications_stay_with_their_user(self):
        from notifications.models import Notification
        from notifications.service import notify

        comm = self._comm(self.other)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await sync_to_async(notify)(self.buyer, Notification.Kind.ORDER_PAID, "Not yours")
        self.assertTrue(await comm.receive_nothing(timeout=0.3))
        await comm.disconnect()

    async def test_token_revoked_by_password_reset_is_rejected(self):
        from django.utils import timezone

        comm = self._comm(self.buyer)  # token minted before the reset
        await sync_to_async(
            User.objects.filter(pk=self.buyer.pk).update
        )(tokens_valid_after=timezone.now())
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

    async def test_non_integer_frame_values_dont_kill_socket(self):
        await self._thread(self.buyer)
        comm = self._comm(self.staff)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        for frame in (
            {"type": "chat.watch", "thread_user_id": "not-a-number"},
            {"type": "chat.typing", "thread_user_id": "not-a-number"},
            {"type": "chat.read", "thread_user_id": [1, 2]},
        ):
            await comm.send_to(text_data=json.dumps(frame))
        msg = await self._msg(await sync_to_async(ChatThread.objects.get)(user=self.buyer),
                              self.buyer, "still open?")
        await sync_to_async(broadcast_message)(msg)
        event = await self._recv_until(
            comm, lambda e: e["type"] == "chat.message" and e["message"]["body"] == "still open?"
        )
        self.assertTrue(event)
        await comm.disconnect()

    async def test_frame_flood_is_throttled(self):
        await self._thread(self.buyer)
        staff_comm = self._comm(self.staff)
        connected, _ = await staff_comm.connect()
        self.assertTrue(connected)
        buyer_comm = self._comm(self.buyer)
        connected, _ = await buyer_comm.connect()
        self.assertTrue(connected)
        await buyer_comm.send_to(text_data=json.dumps({"type": "chat.typing"}))
        await buyer_comm.send_to(text_data=json.dumps({"type": "chat.typing"}))  # < gap: dropped
        event = await self._recv_until(staff_comm, lambda e: e["type"] == "chat.typing")
        self.assertEqual(event["user_id"], self.buyer.id)
        self.assertTrue(await staff_comm.receive_nothing(timeout=0.3))
        await buyer_comm.disconnect()
        await staff_comm.disconnect()

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

    # Presence tests stay single-hop: multi-phase choreography trips the
    # harness's app-task lifecycle, and the offline broadcast is the same
    # _staff_feed call as online (asserted via the registry instead).

    async def test_buyer_presence_reaches_watching_staff(self):
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
        # the watch reply first reports the current (offline) state
        event = await self._recv_until(
            staff_comm,
            lambda e: e["type"] == "chat.presence"
            and e["user_id"] == self.buyer.id
            and e["online"],
        )
        self.assertTrue(event["online"])
        await buyer_comm.disconnect(timeout=5)
        await staff_comm.disconnect(timeout=5)

    async def test_staff_presence_reaches_buyer_thread(self):
        await self._thread(self.buyer)
        buyer_comm = self._comm(self.buyer)
        connected, _ = await buyer_comm.connect()
        self.assertTrue(connected)
        staff_comm = self._comm(self.staff)
        connected, _ = await staff_comm.connect()
        self.assertTrue(connected)
        await staff_comm.send_to(
            text_data=json.dumps({"type": "chat.watch", "thread_user_id": self.buyer.id})
        )
        event = await self._recv_until(
            buyer_comm,
            lambda e: e["type"] == "chat.presence" and e["user_id"] == self.staff.id,
        )
        self.assertTrue(event["online"])
        await staff_comm.disconnect(timeout=5)
        await buyer_comm.disconnect(timeout=5)

    async def test_staff_read_covers_deleted_sender_messages(self):
        thread = await self._thread(self.buyer)
        ghost = await self._msg(thread, None, "ghost message")
        comm = self._comm(self.staff)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await comm.send_to(
            text_data=json.dumps({"type": "chat.read", "thread_user_id": self.buyer.id})
        )
        await self._recv_until(comm, lambda e: e["type"] == "chat.read")
        reloaded = await sync_to_async(ChatMessage.objects.get)(pk=ghost.pk)
        self.assertIsNotNone(reloaded.read_at)
        await comm.disconnect()

    async def test_presence_counts_connections_not_sockets(self):
        # Multiple tabs count; "offline" only fires (broadcast-side) when the
        # last one closes. Registry asserts directly — no teardown flakiness.
        await self._thread(self.buyer)
        buyer1 = self._comm(self.buyer)
        connected, _ = await buyer1.connect()
        self.assertTrue(connected)
        buyer2 = self._comm(self.buyer)
        connected, _ = await buyer2.connect()
        self.assertTrue(connected)
        self.assertEqual(presence.connection_count(self.buyer.id), 2)
        await buyer1.disconnect()
        self.assertEqual(presence.connection_count(self.buyer.id), 1)  # tab 2 still live
        await buyer2.disconnect()
        self.assertEqual(presence.connection_count(self.buyer.id), 0)

    async def test_offline_fires_once_on_last_tab_close(self):
        await self._thread(self.buyer)
        staff_comm = self._comm(self.staff)
        connected, _ = await staff_comm.connect()
        self.assertTrue(connected)
        buyer1 = self._comm(self.buyer)
        connected, _ = await buyer1.connect()
        self.assertTrue(connected)
        await self._recv_until(
            staff_comm, lambda e: e["type"] == "chat.presence" and e["user_id"] == self.buyer.id
        )
        buyer2 = self._comm(self.buyer)
        connected, _ = await buyer2.connect()
        self.assertTrue(connected)
        await buyer1.disconnect()
        # tab 2 still live: no offline broadcast, count stays at 1
        self.assertTrue(await staff_comm.receive_nothing(timeout=0.3))
        self.assertEqual(presence.connection_count(self.buyer.id), 1)
        await buyer2.disconnect()
        await staff_comm.disconnect()

    async def test_watch_reports_current_presence(self):
        # Presence events fire on transitions only, so a staff member opening
        # a thread must get the customer's *current* state with the watch.
        await self._thread(self.buyer)
        buyer_comm = self._comm(self.buyer)
        connected, _ = await buyer_comm.connect()
        self.assertTrue(connected)
        staff_comm = self._comm(self.staff)
        connected, _ = await staff_comm.connect()
        self.assertTrue(connected)
        await staff_comm.send_to(
            text_data=json.dumps({"type": "chat.watch", "thread_user_id": self.buyer.id})
        )
        event = await self._recv_until(
            staff_comm,
            lambda e: e["type"] == "chat.presence" and e["user_id"] == self.buyer.id,
        )
        self.assertTrue(event["online"])
        await buyer_comm.disconnect(timeout=5)
        await staff_comm.disconnect(timeout=5)
    async def test_cross_site_origin_rejected(self):
        """Browser-origin check: a hostile page's handshake is denied even with
        a valid token; origin-less (non-browser) clients are unaffected."""
        token = str(AccessToken.for_user(self.buyer))
        comm = WebsocketCommunicator(
            application,
            f"/ws/chat/?token={token}",
            headers=[(b"origin", b"https://evil.example")],
        )
        connected, _ = await comm.connect()
        self.assertFalse(connected)

    async def test_allowed_host_origin_accepted(self):
        token = str(AccessToken.for_user(self.buyer))
        comm = WebsocketCommunicator(
            application,
            f"/ws/chat/?token={token}",
            headers=[(b"origin", b"http://localhost:3000")],
        )
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await comm.disconnect(timeout=5)


class PresenceContract:
    """What the consumer relies on — "first connection? last one? online?" —
    and so what every presence store must do."""

    def make_store(self):
        raise NotImplementedError

    def setUp(self):
        self.store = self.make_store()

    def test_first_connect_and_last_disconnect_are_the_transitions(self):
        self.assertTrue(self.store.connect(1, "tab-a"))
        self.assertFalse(self.store.connect(1, "tab-b"))
        self.assertFalse(self.store.disconnect(1, "tab-a"))
        self.assertTrue(self.store.is_online(1))
        self.assertTrue(self.store.disconnect(1, "tab-b"))
        self.assertFalse(self.store.is_online(1))

    def test_connections_are_tracked_by_name_not_count(self):
        self.store.connect(1, "tab-a")
        self.store.connect(1, "tab-b")
        # A repeated disconnect of the same tab must not take the other down.
        self.store.disconnect(1, "tab-a")
        self.assertFalse(self.store.disconnect(1, "tab-a"))
        self.assertEqual(self.store.connection_count(1), 1)

    def test_disconnect_without_connect_is_not_a_transition(self):
        self.assertFalse(self.store.disconnect(2, "ghost"))

    def test_users_are_independent(self):
        self.store.connect(1, "a")
        self.assertFalse(self.store.is_online(2))


class InMemoryPresenceTests(PresenceContract, SimpleTestCase):
    def make_store(self):
        from chat.presence import InMemoryPresence

        return InMemoryPresence()


@skipUnless(settings.REDIS_URL, "needs Redis (runs in the Redis CI job)")
class RedisPresenceTests(PresenceContract, SimpleTestCase):
    """The shared store: what one worker records, every worker sees."""

    PREFIX = "test-presence:"

    def make_store(self, **kwargs):
        from chat.presence import RedisPresence
        from core.redis_urls import with_db

        store = RedisPresence(
            with_db(settings.REDIS_URL, settings.REDIS_CHANNELS_DB), prefix=self.PREFIX, **kwargs
        )
        store.clear()
        self.addCleanup(store.clear)
        return store

    def test_other_workers_see_the_connection(self):
        # Two store instances = two worker processes sharing one Redis.
        worker_b = self.make_store()
        self.store.connect(1, "tab-on-a")
        self.assertTrue(worker_b.is_online(1))

    def test_closing_a_tab_on_one_worker_keeps_the_user_online(self):
        worker_b = self.make_store()
        self.assertTrue(self.store.connect(1, "tab-on-a"))
        self.assertFalse(worker_b.connect(1, "tab-on-b"))  # not first: A has one
        self.assertFalse(self.store.disconnect(1, "tab-on-a"))  # B's tab is still open
        self.assertTrue(worker_b.is_online(1))
        self.assertTrue(worker_b.disconnect(1, "tab-on-b"))

    def test_entries_older_than_the_cutoff_are_ignored(self):
        now = [1_000_000.0]
        store = self.make_store(stale_after=90, clock=lambda: now[0])
        store.connect(1, "crashed-worker-tab")
        now[0] += 120  # the worker died without disconnecting
        self.assertFalse(store.is_online(1))
        self.assertTrue(store.connect(1, "fresh-tab"))  # first again: the stale one is pruned

    def test_redis_down_degrades_quietly(self):
        from chat.presence import RedisPresence

        down = RedisPresence("redis://192.0.2.1:6379/0", connect_timeout=0.2)
        self.assertFalse(down.connect(1, "tab"))
        self.assertFalse(down.disconnect(1, "tab"))
        self.assertFalse(down.is_online(1))


@skipUnless(settings.REDIS_URL, "needs Redis (runs in the Redis CI job)")
class RedisPresenceHeartbeatTests(SimpleTestCase):
    """With the 90s cutoff, only the heartbeat keeps an idle tab online."""

    def setUp(self):
        from chat.presence import RedisPresence
        from core.redis_urls import with_db

        self.now = [1_000_000.0]
        self.store = RedisPresence(
            with_db(settings.REDIS_URL, settings.REDIS_CHANNELS_DB),
            prefix="test-heartbeat:", stale_after=90, clock=lambda: self.now[0],
        )
        self.store.clear()
        self.addCleanup(self.store.clear)

    def test_pings_keep_an_idle_connection_online(self):
        self.store.connect(1, "tab")
        for _ in range(4):  # 4 × 60s: well past the cutoff without pings
            self.now[0] += 60
            self.store.touch(1, "tab")
        self.assertTrue(self.store.is_online(1))

    def test_without_pings_it_ages_out(self):
        self.store.connect(1, "tab")
        self.now[0] += 120
        self.assertFalse(self.store.is_online(1))

    def test_a_ping_cannot_resurrect_a_closed_connection(self):
        self.store.connect(1, "tab")
        self.store.disconnect(1, "tab")
        self.store.touch(1, "tab")  # late ping from a socket already gone
        self.assertFalse(self.store.is_online(1))


class ChatPingFrameTests(TransactionTestCase):
    async def test_ping_frame_refreshes_presence(self):
        user = await sync_to_async(User.objects.create_user)(
            username="pinger", email="pinger@example.com", password="pw-123456"
        )
        comm = WebsocketCommunicator(
            application, f"/ws/chat/?token={AccessToken.for_user(user)}"
        )
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        with patch.object(presence, "touch") as touch:
            await comm.send_json_to({"type": "chat.ping"})
            await comm.receive_nothing(timeout=0.2)  # let the frame be handled
        touch.assert_called_once()
        self.assertEqual(touch.call_args.args[0], user.id)
        await comm.disconnect()
