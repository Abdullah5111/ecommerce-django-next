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
