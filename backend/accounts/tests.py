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

    def test_code_is_burned_after_too_many_wrong_attempts(self):
        self.client.post(
            "/api/auth/phone/send-code/", {"phone": "+15551234567"}, format="json"
        )
        good_code = self._sent_code()
        for _ in range(5):
            self.client.post(
                "/api/auth/phone/verify/", {"code": "000000"}, format="json"
            )
        # the real code no longer works once the attempt limit is hit
        res = self.client.post(
            "/api/auth/phone/verify/", {"code": good_code}, format="json"
        )
        self.assertEqual(res.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.phone_verified)

    def test_phone_already_verified_by_another_user_is_rejected(self):
        User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="pw-123456",
            phone="+15551234567",
            phone_verified=True,
        )
        self.client.post(
            "/api/auth/phone/send-code/", {"phone": "+15551234567"}, format="json"
        )
        res = self.client.post(
            "/api/auth/phone/verify/", {"code": self._sent_code()}, format="json"
        )
        self.assertEqual(res.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.phone_verified)


from unittest.mock import patch

from accounts import google

GOOGLE_ENABLED = dict(GOOGLE_OAUTH_CLIENT_ID="test-client-id.apps.googleusercontent.com")

VALID_CLAIMS = {
    "iss": "https://accounts.google.com",
    "email": "ada@example.com",
    "email_verified": True,
    "name": "Ada Lovelace",
    "sub": "google-uid-1",
}


class GoogleVerifyTests(APITestCase):
    def test_disabled_when_no_client_id(self):
        self.assertFalse(google.is_enabled())
        with self.assertRaises(google.GoogleAuthError):
            google.verify_id_token("anything")

    @override_settings(**GOOGLE_ENABLED)
    def test_valid_token_returns_claims(self):
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=VALID_CLAIMS):
            claims = google.verify_id_token("good-token")
        self.assertEqual(claims["email"], "ada@example.com")

    @override_settings(**GOOGLE_ENABLED)
    def test_invalid_token_raises(self):
        with patch("google.oauth2.id_token.verify_oauth2_token", side_effect=ValueError("bad")):
            with self.assertRaises(google.GoogleAuthError):
                google.verify_id_token("bad-token")

    @override_settings(**GOOGLE_ENABLED)
    def test_untrusted_issuer_rejected(self):
        bad = {**VALID_CLAIMS, "iss": "evil.example.com"}
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=bad):
            with self.assertRaises(google.GoogleAuthError):
                google.verify_id_token("token")

    @override_settings(**GOOGLE_ENABLED)
    def test_unverified_email_rejected(self):
        bad = {**VALID_CLAIMS, "email_verified": False}
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=bad):
            with self.assertRaises(google.GoogleAuthError):
                google.verify_id_token("token")


class GoogleConfigTests(APITestCase):
    def test_config_disabled_by_default(self):
        res = self.client.get("/api/auth/google/config/")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["enabled"])
        self.assertEqual(res.data["client_id"], "")

    @override_settings(**GOOGLE_ENABLED)
    def test_config_enabled_exposes_client_id(self):
        res = self.client.get("/api/auth/google/config/")
        self.assertTrue(res.data["enabled"])
        self.assertEqual(res.data["client_id"], "test-client-id.apps.googleusercontent.com")
