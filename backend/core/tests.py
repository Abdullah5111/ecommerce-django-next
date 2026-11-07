from unittest import skipUnless

from django.conf import settings
from django.test import SimpleTestCase, TestCase


class HealthCheckTests(SimpleTestCase):
    def test_health_returns_ok(self):
        res = self.client.get("/api/health/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "ok"})


class ApiDocsTests(TestCase):
    def test_openapi_schema_builds(self):
        # A 200 here means drf-spectacular introspected every view without error.
        res = self.client.get("/api/schema/")
        self.assertEqual(res.status_code, 200)

    def test_swagger_ui_is_served(self):
        self.assertEqual(self.client.get("/api/docs/").status_code, 200)


class RedisUrlTests(SimpleTestCase):
    """The cache and the Channels layer share one REDIS_URL but must land on
    different logical databases (a cache FLUSHDB would drop WebSocket groups)."""

    def test_replaces_the_database(self):
        from core.redis_urls import with_db

        self.assertEqual(with_db("redis://redis:6379/0", 1), "redis://redis:6379/1")

    def test_adds_a_database_when_the_url_has_none(self):
        from core.redis_urls import with_db

        self.assertEqual(with_db("redis://10.0.0.3:6379", 1), "redis://10.0.0.3:6379/1")

    def test_keeps_credentials_tls_and_options(self):
        from core.redis_urls import with_db

        self.assertEqual(
            with_db("rediss://:secret@cache.example.com:6380/0?ssl_cert_reqs=none", 2),
            "rediss://:secret@cache.example.com:6380/2?ssl_cert_reqs=none",
        )


# TEST-NET-1 (RFC 5737): never routed, so a connect either times out or is
# refused at once — it must not hang for the OS TCP timeout.
UNREACHABLE_REDIS = "redis://192.0.2.1:6379/1"


class RedisTimeoutTests(SimpleTestCase):
    """An unreachable Redis fails within the configured timeouts instead of
    hanging the request for minutes."""

    def test_cache_fails_fast(self):
        import time

        from django.core.cache.backends.redis import RedisCache
        from redis.exceptions import RedisError

        cache = RedisCache(
            UNREACHABLE_REDIS,
            {"OPTIONS": {
                "socket_connect_timeout": settings.REDIS_CONNECT_TIMEOUT,
                "socket_timeout": settings.REDIS_SOCKET_TIMEOUT,
            }},
        )
        started = time.monotonic()
        with self.assertRaises(RedisError):
            cache.get("anything")
        self.assertLess(time.monotonic() - started, 5)

    def test_channel_layer_connect_fails_fast(self):
        import asyncio
        import time

        from channels_redis.utils import create_pool
        from redis import asyncio as aioredis
        from redis.exceptions import RedisError

        # Same host shape settings.CHANNEL_LAYERS uses when REDIS_URL is set.
        pool = create_pool({
            "address": UNREACHABLE_REDIS,
            "socket_connect_timeout": settings.REDIS_CONNECT_TIMEOUT,
        })

        async def ping():
            client = aioredis.Redis(connection_pool=pool)
            try:
                await client.ping()
            finally:
                await client.aclose()

        started = time.monotonic()
        with self.assertRaises(RedisError):
            asyncio.run(ping())
        self.assertLess(time.monotonic() - started, 5)


class ReadinessTests(TestCase):
    """/api/ready/: 200 when the database (and Redis, if configured) answer,
    503 naming what doesn't."""

    def test_ready_when_dependencies_answer(self):

        res = self.client.get("/api/ready/")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["checks"]["database"], "ok")
        # Redis checks appear only when REDIS_URL is set (the Redis CI job).
        self.assertEqual("cache" in body["checks"], bool(settings.REDIS_URL))

    def test_database_down_is_503(self):
        from unittest.mock import patch

        from django.db import OperationalError

        with patch("core.views._check_database", side_effect=OperationalError("gone")):
            res = self.client.get("/api/ready/")
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()["checks"]["database"], "unavailable")

    def test_redis_down_is_503_and_names_the_part(self):
        from unittest.mock import patch

        from django.test import override_settings
        from redis.exceptions import ConnectionError as RedisConnectionError

        down = RedisConnectionError("Connection refused")
        with override_settings(REDIS_URL="redis://cache.internal:6379/0"), \
                patch("core.views._check_cache", side_effect=down), \
                patch("core.views._check_channel_layer"):
            res = self.client.get("/api/ready/")
        self.assertEqual(res.status_code, 503)
        self.assertEqual(
            res.json()["checks"],
            {"database": "ok", "cache": "unavailable", "channel_layer": "ok"},
        )

    def test_failure_details_are_not_exposed(self):
        from unittest.mock import patch

        with patch("core.views._check_database", side_effect=RuntimeError("password=hunter2")):
            res = self.client.get("/api/ready/")
        self.assertNotIn("hunter2", res.content.decode())

    def test_channel_layer_probe_runs_against_the_configured_layer(self):
        # Real call: InMemory layer here, Redis in the Redis CI job.
        from core.views import _check_channel_layer

        _check_channel_layer()


class RedisConfiguredCheckTests(SimpleTestCase):
    """core.W001: a non-DEBUG run without REDIS_URL gets a warning — not an
    error, so a deliberate single-instance deploy still starts."""

    def _ids(self):
        from core.checks import check_redis_configured

        return [w.id for w in check_redis_configured(None)]

    def test_warns_without_redis_outside_debug(self):
        from django.test import override_settings

        with override_settings(DEBUG=False, REDIS_URL=""):
            self.assertEqual(self._ids(), ["core.W001"])

    def test_silent_with_redis(self):
        from django.test import override_settings

        with override_settings(DEBUG=False, REDIS_URL="redis://redis:6379/0"):
            self.assertEqual(self._ids(), [])

    def test_silent_in_debug(self):
        from django.test import override_settings

        with override_settings(DEBUG=True, REDIS_URL=""):
            self.assertEqual(self._ids(), [])

    def test_registered_with_the_check_framework(self):
        from django.core import checks
        from django.test import override_settings

        with override_settings(DEBUG=False, REDIS_URL=""):
            ids = [m.id for m in checks.run_checks()]
        self.assertIn("core.W001", ids)

    def test_startup_log_matches_and_respects_silencing(self):
        from django.test import override_settings

        from core.checks import warn_at_startup

        with override_settings(DEBUG=False, REDIS_URL=""):
            with self.assertLogs("core.checks", level="WARNING") as logs:
                warn_at_startup()
        self.assertIn("REDIS_URL is not set", logs.output[0])

        with override_settings(DEBUG=False, REDIS_URL="", SILENCED_SYSTEM_CHECKS=["core.W001"]):
            with self.assertNoLogs("core.checks", level="WARNING"):
                warn_at_startup()


class TolerantRedisCacheTests(SimpleTestCase):
    """With Redis unreachable, the default cache misses and skips instead of
    raising — so catalog pages and rate-limited endpoints keep working."""

    def setUp(self):
        import core.cache
        from core.cache import TolerantRedisCache

        core.cache._last_warning = 0.0  # module state: start each test fresh
        self.cache = TolerantRedisCache(
            UNREACHABLE_REDIS,
            {"OPTIONS": {"socket_connect_timeout": 0.2, "socket_timeout": 0.2}},
        )

    def test_reads_miss(self):
        self.assertEqual(self.cache.get("k", "fallback"), "fallback")
        self.assertEqual(self.cache.get_many(["a", "b"]), {})
        self.assertFalse(self.cache.has_key("k"))

    def test_writes_are_skipped(self):
        self.cache.set("k", 1)
        self.assertFalse(self.cache.add("k", 1))
        self.assertEqual(self.cache.set_many({"a": 1, "b": 2}), ["a", "b"])
        self.assertFalse(self.cache.delete("k"))
        self.cache.delete_many(["a"])
        self.assertFalse(self.cache.touch("k"))

    def test_get_or_set_falls_back_to_computing(self):
        self.assertEqual(self.cache.get_or_set("k", lambda: 42), 42)

    def test_incr_behaves_like_a_missing_key(self):
        with self.assertRaises(ValueError):
            self.cache.incr("counter")

    def test_warns_once_per_window_not_per_call(self):
        with self.assertLogs("core.cache", level="WARNING") as logs:
            for _ in range(3):
                self.cache.get("k")
        self.assertEqual(len(logs.output), 1)


@skipUnless(settings.REDIS_URL, "needs Redis (runs in the Redis CI job)")
class CacheAliasWiringTests(SimpleTestCase):
    def test_default_tolerates_outages_and_otp_does_not(self):
        from django.core.cache import caches

        from core.cache import TolerantRedisCache

        self.assertIsInstance(caches["default"], TolerantRedisCache)
        self.assertNotIsInstance(caches["otp"], TolerantRedisCache)


@skipUnless(settings.REDIS_URL, "needs Redis (runs in the Redis CI job)")
class RedisOutageTests(TestCase):
    """End to end with Redis down: the site keeps working, rate limits switch
    off, and only phone verification (strict, fail-closed) refuses."""

    def setUp(self):
        from decimal import Decimal
        from unittest.mock import patch

        from django.contrib.auth import get_user_model
        from django.core.cache import cache
        from redis.exceptions import ConnectionError as RedisConnectionError
        from rest_framework.test import APIClient

        from products.models import Category, Product

        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="down", email="down@example.com", password="pw-123456"
        )
        category = Category.objects.create(name="Gear")
        Product.objects.create(
            name="Widget", price=Decimal("10.00"), stock=5, category=category, is_featured=True
        )
        self.api = APIClient()
        # Every cache call (both aliases) goes through get_client.
        outage = patch(
            "django.core.cache.backends.redis.RedisCacheClient.get_client",
            side_effect=RedisConnectionError("Redis is down"),
        )
        outage.start()
        self.addCleanup(outage.stop)

    def _login(self):
        return self.api.post(
            "/api/auth/token/", {"username": "down", "password": "pw-123456"}, format="json"
        )

    def test_login_still_works(self):
        self.assertEqual(self._login().status_code, 200)

    def test_sign_up_still_works(self):
        res = self.api.post(
            "/api/auth/register/",
            {"username": "newbie", "email": "newbie@example.com", "password": "s7rong-p4ss-x9"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)

    def test_rate_limits_switch_off_rather_than_lock_everyone_out(self):
        from unittest.mock import patch

        from rest_framework.throttling import ScopedRateThrottle

        with patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"auth-login": "1/min"}):
            codes = [self._login().status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 200])

    def test_catalog_pages_fall_back_to_the_database(self):
        res = self.api.get("/api/products/featured/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual([p["name"] for p in res.json()], ["Widget"])
        self.assertEqual(self.api.get("/api/categories/tree/").status_code, 200)

    def test_phone_verification_still_fails_closed(self):
        self.api.force_authenticate(self.user)
        with self.settings(SMS_BACKEND="console"):
            res = self.api.post(
                "/api/auth/phone/send-code/", {"phone": "+15551234567"}, format="json"
            )
        self.assertEqual(res.status_code, 503)

    def test_readiness_reports_the_cache_down(self):
        res = self.api.get("/api/ready/")
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()["checks"]["cache"], "unavailable")
