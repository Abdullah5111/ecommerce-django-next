import io
import tempfile

from django.contrib.auth import get_user_model
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
