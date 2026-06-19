from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from products.models import Category, Product
from wishlist.models import WishlistItem

User = get_user_model()


class WishlistTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.p1 = Product.objects.create(name="A", price=Decimal("10.00"), stock=5, category=self.cat)
        self.p2 = Product.objects.create(name="B", price=Decimal("20.00"), stock=5, category=self.cat)
        self.user = User.objects.create_user(username="u", email="u@example.com", password="pw-123456")
        self.client.force_authenticate(self.user)

    def test_add_is_idempotent(self):
        self.client.post("/api/wishlist/items/", {"product": self.p1.id}, format="json")
        res = self.client.post("/api/wishlist/items/", {"product": self.p1.id}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["product"]["id"], self.p1.id)

    def test_remove(self):
        self.client.post("/api/wishlist/items/", {"product": self.p1.id}, format="json")
        res = self.client.delete(f"/api/wishlist/items/{self.p1.id}/")
        self.assertEqual(res.data, [])

    def test_merge_unions(self):
        self.client.post("/api/wishlist/items/", {"product": self.p1.id}, format="json")
        res = self.client.post("/api/wishlist/merge/", {"product_ids": [self.p1.id, self.p2.id]}, format="json")
        ids = {row["product"]["id"] for row in res.data}
        self.assertEqual(ids, {self.p1.id, self.p2.id})  # union, no duplicate of p1

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/wishlist/").status_code, 401)

    def test_users_have_separate_wishlists(self):
        self.client.post("/api/wishlist/items/", {"product": self.p1.id}, format="json")
        other = User.objects.create_user(username="o", email="o@example.com", password="pw-123456")
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get("/api/wishlist/").data, [])
