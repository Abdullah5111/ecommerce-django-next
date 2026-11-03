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
