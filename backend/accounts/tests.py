import io
import tempfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

User = get_user_model()

MEDIA_ROOT = tempfile.mkdtemp()


def make_image(fmt="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "blue").save(buf, format=fmt)
    buf.seek(0)
    buf.name = f"avatar.{fmt.lower()}"
    return buf


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ProfileTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="amy", email="amy@example.com", password="pw-123456"
        )
        self.client.force_authenticate(self.user)

    def test_patch_updates_editable_profile_fields(self):
        res = self.client.patch(
            "/api/auth/me/",
            {"display_name": "Amy", "bio": "hello", "gender": "female"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.display_name, "Amy")
        self.assertEqual(self.user.bio, "hello")
        self.assertEqual(self.user.gender, "female")

    def test_phone_is_read_only_via_me(self):
        res = self.client.patch("/api/auth/me/", {"phone": "12345"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, "")

    def test_avatar_upload_then_delete(self):
        res = self.client.post(
            "/api/auth/me/avatar/", {"avatar": make_image()}, format="multipart"
        )
        self.assertEqual(res.status_code, 200)
        self.assertIsNotNone(res.data["avatar"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)

        res = self.client.delete("/api/auth/me/avatar/")
        self.assertEqual(res.status_code, 204)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_avatar_rejects_non_image(self):
        bad = io.BytesIO(b"this is not an image")
        bad.name = "x.png"
        res = self.client.post(
            "/api/auth/me/avatar/", {"avatar": bad}, format="multipart"
        )
        self.assertEqual(res.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)


class PhoneVerificationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="ben", email="ben@example.com", password="pw-123456"
        )
        self.client.force_authenticate(self.user)

    def _sent_code(self):
        return cache.get(f"phone_otp:{self.user.id}")["code"]

    def test_send_then_verify_sets_phone_and_flag(self):
        res = self.client.post(
            "/api/auth/phone/send-code/", {"phone": "+15551234567"}, format="json"
        )
        self.assertEqual(res.status_code, 200)

        res = self.client.post(
            "/api/auth/phone/verify/", {"code": self._sent_code()}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, "+15551234567")
        self.assertTrue(self.user.phone_verified)

    def test_send_requires_phone(self):
        res = self.client.post("/api/auth/phone/send-code/", {}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_verify_rejects_wrong_code(self):
        self.client.post(
            "/api/auth/phone/send-code/", {"phone": "+15551234567"}, format="json"
        )
        res = self.client.post(
            "/api/auth/phone/verify/", {"code": "000000"}, format="json"
        )
        self.assertEqual(res.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.phone_verified)

    def test_verify_without_a_sent_code_fails(self):
        res = self.client.post(
            "/api/auth/phone/verify/", {"code": "123456"}, format="json"
        )
        self.assertEqual(res.status_code, 400)

    def test_immediate_resend_is_rate_limited(self):
        self.client.post(
            "/api/auth/phone/send-code/", {"phone": "+15551234567"}, format="json"
        )
        res = self.client.post(
            "/api/auth/phone/send-code/", {"phone": "+15551234567"}, format="json"
        )
        self.assertEqual(res.status_code, 429)
