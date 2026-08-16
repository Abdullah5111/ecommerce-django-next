from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from products.models import Category, Product, ProductVariant
from wishlist.models import WishlistItem
from wishlist.views import _wishlist_data

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

    def test_merge_rejects_non_list_product_ids(self):
        res = self.client.post("/api/wishlist/merge/", {"product_ids": "5"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_merge_ignores_malformed_ids(self):
        res = self.client.post(
            "/api/wishlist/merge/",
            {"product_ids": [self.p1.id, "abc", None]},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual({row["product"]["id"] for row in res.data}, {self.p1.id})

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/wishlist/").status_code, 401)

    def test_listing_does_not_n_plus_1_on_variants(self):
        # Each product has a variant, so has_variants/price_from run per row;
        # variants must be prefetched, not queried once per wishlist item.
        for p in (self.p1, self.p2):
            ProductVariant.objects.create(product=p, sku=f"{p.name}-V", price=p.price)
            WishlistItem.objects.create(user=self.user, product=p)
        with self.assertNumQueries(3):  # items(+category join) + images + variants
            _wishlist_data(self.user)

    def test_users_have_separate_wishlists(self):
        self.client.post("/api/wishlist/items/", {"product": self.p1.id}, format="json")
        other = User.objects.create_user(username="o", email="o@example.com", password="pw-123456")
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get("/api/wishlist/").data, [])
