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

        from django.conf import settings
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
        from django.conf import settings
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
        from django.conf import settings

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
