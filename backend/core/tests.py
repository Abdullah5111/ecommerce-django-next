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
