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

from rest_framework.throttling import ScopedRateThrottle

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


class GoogleLoginEndpointTests(APITestCase):
    def _post(self, credential="tok"):
        return self.client.post("/api/auth/google/", {"credential": credential}, format="json")

    def test_disabled_returns_503(self):
        res = self._post()
        self.assertEqual(res.status_code, 503)

    @override_settings(**GOOGLE_ENABLED)
    def test_creates_new_user_and_returns_jwt(self):
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=VALID_CLAIMS):
            res = self._post()
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)
        user = User.objects.get(email="ada@example.com")
        self.assertTrue(user.email_verified)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.display_name, "Ada Lovelace")

    @override_settings(**GOOGLE_ENABLED)
    def test_links_existing_account_by_email(self):
        existing = User.objects.create_user(
            username="ada_pw", email="ada@example.com", password="pw-123456"
        )
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=VALID_CLAIMS):
            res = self._post()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(User.objects.filter(email__iexact="ada@example.com").count(), 1)
        existing.refresh_from_db()
        self.assertTrue(existing.email_verified)
        self.assertTrue(existing.has_usable_password())  # password preserved

    @override_settings(**GOOGLE_ENABLED)
    def test_returning_google_user_is_reused(self):
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=VALID_CLAIMS):
            self._post()
            self._post()
        self.assertEqual(User.objects.filter(email__iexact="ada@example.com").count(), 1)

    @override_settings(**GOOGLE_ENABLED)
    def test_username_collision_gets_suffixed(self):
        User.objects.create_user(username="ada", email="other@example.com", password="pw-123456")
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=VALID_CLAIMS):
            self._post()
        new_user = User.objects.get(email="ada@example.com")
        self.assertNotEqual(new_user.username, "ada")

    @override_settings(**GOOGLE_ENABLED)
    def test_invalid_credential_returns_400(self):
        with patch("google.oauth2.id_token.verify_oauth2_token", side_effect=ValueError("bad")):
            res = self._post("bad")
        self.assertEqual(res.status_code, 400)


class AuthThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()  # throttle history lives in the cache, which TestCase does not roll back
        # override_settings(REST_FRAMEWORK=...) is ignored here: ScopedRateThrottle
        # binds THROTTLE_RATES at class-definition time, so patch the dict it reads.
        rates = patch.dict(
            ScopedRateThrottle.THROTTLE_RATES,
            {"auth-register": "1/hour", "auth-password": "1/hour"},
        )
        rates.start()
        self.addCleanup(rates.stop)

    def test_register_is_throttled_per_ip(self):
        body = lambda n: {"username": f"u{n}", "email": f"u{n}@x.co", "password": "pw-abc12345"}
        self.assertEqual(self.client.post("/api/auth/register/", body(1)).status_code, 201)
        self.assertEqual(self.client.post("/api/auth/register/", body(2)).status_code, 429)

    def test_forgot_password_is_throttled_per_ip(self):
        self.client.post("/api/auth/forgot-password/", {"email": "a@x.co"})
        res = self.client.post("/api/auth/forgot-password/", {"email": "a@x.co"})
        self.assertEqual(res.status_code, 429)


class RegisterPasswordPolicyTests(APITestCase):
    def _register(self, password):
        return self.client.post(
            "/api/auth/register/",
            {"username": "newbie", "email": "newbie@x.co", "password": password},
        )

    def test_common_password_is_rejected(self):
        res = self._register("password")  # on Django's common-password blocklist
        self.assertEqual(res.status_code, 400)
        self.assertFalse(User.objects.filter(username="newbie").exists())

    def test_strong_password_is_accepted(self):
        self.assertEqual(self._register("s7rong-p4ss-x9").status_code, 201)


class PasswordResetRevokesSessionsTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="carol", email="carol@example.com", password="old-pw-12345"
        )

    def _reset_credentials(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        return (
            urlsafe_base64_encode(force_bytes(self.user.pk)),
            default_token_generator.make_token(self.user),
        )

    def test_reset_blacklists_existing_refresh_tokens(self):
        login = self.client.post(
            "/api/auth/token/", {"username": "carol", "password": "old-pw-12345"}
        )
        refresh = login.data["refresh"]
        uid, token = self._reset_credentials()

        res = self.client.post(
            "/api/auth/reset-password/",
            {"uid": uid, "token": token, "new_password": "new-pw-abc-99"},
        )
        self.assertEqual(res.status_code, 200)

        # The pre-reset refresh token can no longer mint access tokens.
        refreshed = self.client.post("/api/auth/token/refresh/", {"refresh": refresh})
        self.assertEqual(refreshed.status_code, 401)
