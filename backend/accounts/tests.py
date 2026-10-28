import io
import tempfile
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from accounts import google

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


@override_settings(SMS_BACKEND="console")
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
        self.assertNotIn("refresh", res.data)  # it's in the httpOnly cookie
        self.assertTrue(res.cookies["refresh_token"]["httponly"])
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
        def body(n):
            return {"username": f"u{n}", "email": f"u{n}@x.co", "password": "pw-abc12345"}

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
        refresh = login.cookies["refresh_token"].value
        uid, token = self._reset_credentials()

        res = self.client.post(
            "/api/auth/reset-password/",
            {"uid": uid, "token": token, "new_password": "new-pw-abc-99"},
        )
        self.assertEqual(res.status_code, 200)

        # The pre-reset refresh token can no longer mint access tokens.
        refreshed = self.client.post("/api/auth/token/refresh/", {"refresh": refresh})
        self.assertEqual(refreshed.status_code, 401)

    def _reset(self):
        uid, token = self._reset_credentials()
        res = self.client.post(
            "/api/auth/reset-password/",
            {"uid": uid, "token": token, "new_password": "new-pw-abc-99"},
        )
        self.assertEqual(res.status_code, 200)

    def test_reset_revokes_existing_access_tokens(self):
        login = self.client.post(
            "/api/auth/token/", {"username": "carol", "password": "old-pw-12345"}
        )
        auth = {"HTTP_AUTHORIZATION": f"Bearer {login.data['access']}"}
        self.assertEqual(self.client.get("/api/auth/me/", **auth).status_code, 200)

        self._reset()

        self.assertEqual(self.client.get("/api/auth/me/", **auth).status_code, 401)

    def test_signing_in_after_the_reset_works(self):
        from datetime import timedelta

        self._reset()
        # Step past the reset's second (iat has one-second resolution).
        self.user.refresh_from_db()
        User.objects.filter(pk=self.user.pk).update(
            tokens_valid_after=self.user.tokens_valid_after - timedelta(seconds=5)
        )
        login = self.client.post(
            "/api/auth/token/", {"username": "carol", "password": "new-pw-abc-99"}
        )
        self.assertEqual(login.status_code, 200)
        auth = {"HTTP_AUTHORIZATION": f"Bearer {login.data['access']}"}
        self.assertEqual(self.client.get("/api/auth/me/", **auth).status_code, 200)

    def test_users_who_never_reset_are_unaffected(self):
        login = self.client.post(
            "/api/auth/token/", {"username": "carol", "password": "old-pw-12345"}
        )
        auth = {"HTTP_AUTHORIZATION": f"Bearer {login.data['access']}"}
        self.assertEqual(self.client.get("/api/auth/me/", **auth).status_code, 200)


class MeStaffFlagTests(APITestCase):
    """is_staff is exposed for the staff-inbox UI — and must be read-only,
    or PATCH /auth/me/ {"is_staff": true} would be a privilege hole."""

    def test_is_staff_exposed_but_not_writable(self):
        user = User.objects.create_user(
            username="pleb", email="pleb@example.com", password="pw-123456"
        )
        self.client.force_authenticate(user)
        res = self.client.get("/api/auth/me/")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["is_staff"])
        res = self.client.patch("/api/auth/me/", {"is_staff": True}, format="json")
        self.assertEqual(res.status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.is_staff)


@override_settings(SMS_BACKEND="console")
class PhoneVerifyInputValidationTests(APITestCase):
    """Regression: non-ASCII or non-string codes used to raise TypeError in
    hmac.compare_digest and return a 500 instead of a 400."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="otpuser", email="otp@example.com", password="pw-123456"
        )
        self.client.force_authenticate(self.user)
        cache.clear()
        self.client.post("/api/auth/phone/send-code/", {"phone": "+15551234567"}, format="json")

    def test_non_ascii_code_is_rejected_not_500(self):
        res = self.client.post("/api/auth/phone/verify/", {"code": "１２３４５６"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_non_numeric_code_is_rejected(self):
        res = self.client.post("/api/auth/phone/verify/", {"code": "abc-€"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_integer_code_body_does_not_500(self):
        res = self.client.post("/api/auth/phone/verify/", {"code": 123456}, format="json")
        self.assertEqual(res.status_code, 400)


class TokenEndpointThrottleTests(APITestCase):
    """Refresh and logout are unauthenticated token endpoints; they share one
    per-IP 'auth-token' bucket so neither can be hammered unbounded."""

    def setUp(self):
        cache.clear()  # throttle history lives in the cache — not rolled back
        rates = patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"auth-token": "2/min"})
        rates.start()
        self.addCleanup(rates.stop)

    def test_refresh_is_throttled(self):
        for _ in range(2):
            res = self.client.post("/api/auth/token/refresh/", {"refresh": "junk"})
            self.assertEqual(res.status_code, 401)
        res = self.client.post("/api/auth/token/refresh/", {"refresh": "junk"})
        self.assertEqual(res.status_code, 429)

    def test_logout_shares_the_bucket(self):
        self.client.post("/api/auth/token/refresh/", {"refresh": "junk"})
        self.client.post("/api/auth/logout/", {"refresh": "junk"})
        res = self.client.post("/api/auth/logout/", {"refresh": "junk"})
        self.assertEqual(res.status_code, 429)


@override_settings(SMS_BACKEND="console")
class PhoneOtpThrottleTests(APITestCase):
    """The 30s cooldown and the per-code attempt limit don't cap anything over
    time on their own — a new code every 30s meant ~10 guesses a minute,
    indefinitely. Per-user throttles do."""

    def setUp(self):
        cache.clear()  # throttle history lives in the cache — not rolled back
        rates = patch.dict(
            ScopedRateThrottle.THROTTLE_RATES,
            {"auth-phone-send": "2/hour", "auth-phone-verify": "2/hour"},
        )
        rates.start()
        self.addCleanup(rates.stop)
        self.user = User.objects.create_user(
            username="otp", email="otp@example.com", password="pw-123456"
        )
        self.client.force_authenticate(self.user)

    def _send(self):
        # Skip the 30s cooldown so only the throttle can refuse.
        cache.delete(f"phone_otp_cooldown:{self.user.id}")
        return self.client.post(
            "/api/auth/phone/send-code/", {"phone": "+15551234567"}, format="json"
        )

    def _guess(self):
        return self.client.post("/api/auth/phone/verify/", {"code": "000000"}, format="json")

    def test_sends_are_capped_past_the_cooldown(self):
        self.assertEqual(self._send().status_code, 200)
        self.assertEqual(self._send().status_code, 200)
        res = self._send()
        self.assertEqual(res.status_code, 429)
        self.assertIn("throttled", str(res.data["detail"]))

    def test_guesses_are_capped_across_codes(self):
        self._send()
        self.assertEqual(self._guess().status_code, 400)
        self.assertEqual(self._guess().status_code, 400)
        self.assertEqual(self._guess().status_code, 429)

    def test_limits_are_per_user(self):
        self._send()
        self._send()
        other = User.objects.create_user(
            username="otp2", email="otp2@example.com", password="pw-123456"
        )
        self.client.force_authenticate(other)
        res = self.client.post(
            "/api/auth/phone/send-code/", {"phone": "+15557654321"}, format="json"
        )
        self.assertEqual(res.status_code, 200)


TWILIO = dict(
    SMS_BACKEND="twilio",
    TWILIO_ACCOUNT_SID="AC123",
    TWILIO_AUTH_TOKEN="secret",
    TWILIO_FROM_NUMBER="+15550000000",
    TWILIO_MESSAGING_SERVICE_SID="",
)


class SmsProviderTests(APITestCase):
    """send-code texts through accounts.sms, and stores a code only once the
    provider accepted the message."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="sms", email="sms@example.com", password="pw-123456"
        )
        self.client.force_authenticate(self.user)

    def _send(self, phone="+15551234567"):
        return self.client.post("/api/auth/phone/send-code/", {"phone": phone}, format="json")

    def _stored(self):
        return cache.get(f"phone_otp:{self.user.id}")

    @override_settings(SMS_BACKEND="")
    def test_unconfigured_provider_refuses_instead_of_pretending(self):
        self.assertEqual(self._send().status_code, 503)
        self.assertIsNone(self._stored())

    @override_settings(SMS_BACKEND="console")
    def test_number_must_be_e164_after_stripping_punctuation(self):
        self.assertEqual(self._send("5551234567").status_code, 400)
        self.assertEqual(self._send("+1 (555) 123-4567").status_code, 200)
        self.assertEqual(self._stored()["phone"], "+15551234567")

    @override_settings(**TWILIO)
    def test_twilio_receives_the_code(self):
        import json
        from urllib.parse import parse_qs

        response = MagicMock()
        response.read.return_value = json.dumps({"sid": "SM1"}).encode()
        response.__enter__.return_value = response
        with patch("accounts.sms.urllib.request.urlopen", return_value=response) as urlopen:
            self.assertEqual(self._send().status_code, 200)
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url, "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json"
        )
        self.assertTrue(request.get_header("Authorization").startswith("Basic "))
        fields = parse_qs(request.data.decode())
        self.assertEqual(fields["To"], ["+15551234567"])
        self.assertEqual(fields["From"], ["+15550000000"])
        self.assertIn(self._stored()["code"], fields["Body"][0])

    @override_settings(**{**TWILIO, "TWILIO_MESSAGING_SERVICE_SID": "MG9"})
    def test_messaging_service_is_preferred_over_from_number(self):
        from urllib.parse import parse_qs

        response = MagicMock()
        response.read.return_value = b"{}"
        response.__enter__.return_value = response
        with patch("accounts.sms.urllib.request.urlopen", return_value=response) as urlopen:
            self._send()
        fields = parse_qs(urlopen.call_args.args[0].data.decode())
        self.assertEqual(fields["MessagingServiceSid"], ["MG9"])
        self.assertNotIn("From", fields)

    @override_settings(**TWILIO)
    def test_provider_error_stores_nothing_so_the_user_can_retry(self):
        from urllib.error import HTTPError

        error = HTTPError(
            "https://api.twilio.com", 400, "Bad Request", {}, io.BytesIO(b'{"code": 21211}')
        )
        with patch("accounts.sms.urllib.request.urlopen", side_effect=error):
            self.assertEqual(self._send().status_code, 502)
        self.assertIsNone(self._stored())
        self.assertIsNone(cache.get(f"phone_otp_cooldown:{self.user.id}"))


class RefreshCookieTests(APITestCase):
    """The refresh token travels only in an httpOnly cookie; the browser's JS
    sees just the access token."""

    FETCH = {"HTTP_X_REQUESTED_WITH": "fetch"}

    def setUp(self):
        cache.clear()
        User.objects.create_user(
            username="cookie", email="cookie@example.com", password="pw-123456"
        )

    def _login(self):
        res = self.client.post(
            "/api/auth/token/", {"username": "cookie", "password": "pw-123456"}
        )
        self.assertEqual(res.status_code, 200)
        return res

    def test_login_sets_an_httponly_cookie_and_keeps_refresh_out_of_the_body(self):
        res = self._login()
        self.assertIn("access", res.data)
        self.assertNotIn("refresh", res.data)
        cookie = res.cookies["refresh_token"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["path"], "/api/auth/")
        self.assertEqual(cookie["samesite"], "Lax")

    def test_refresh_from_cookie_returns_access_and_rotates_the_cookie(self):
        first = self._login().cookies["refresh_token"].value
        res = self.client.post("/api/auth/token/refresh/", **self.FETCH)
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertNotIn("refresh", res.data)
        self.assertNotEqual(res.cookies["refresh_token"].value, first)

    def test_cookie_is_ignored_without_the_fetch_header(self):
        # A cross-site form post can't set custom headers, so it gets nothing.
        self._login()
        res = self.client.post("/api/auth/token/refresh/")
        self.assertNotEqual(res.status_code, 200)

    def test_logout_blacklists_and_clears_the_cookie(self):
        token = self._login().cookies["refresh_token"].value
        res = self.client.post("/api/auth/logout/", **self.FETCH)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.cookies["refresh_token"].value, "")
        reused = self.client.post("/api/auth/token/refresh/", {"refresh": token})
        self.assertEqual(reused.status_code, 401)

    def test_dead_cookie_is_cleared(self):
        self.client.cookies["refresh_token"] = "not-a-token"
        res = self.client.post("/api/auth/token/refresh/", **self.FETCH)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.cookies["refresh_token"].value, "")

    def test_body_token_still_works_for_api_clients(self):
        token = self._login().cookies["refresh_token"].value
        self.client.cookies.clear()
        res = self.client.post("/api/auth/token/refresh/", {"refresh": token})
        self.assertEqual(res.status_code, 200)
        self.assertIn("refresh", res.data)  # rotated token goes back the way it came
