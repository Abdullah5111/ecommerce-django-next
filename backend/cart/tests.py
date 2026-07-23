from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from cart.models import Cart, CartItem
from products.models import Category, Product

User = get_user_model()


class CartTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.p = Product.objects.create(name="Widget", price=Decimal("40.00"), stock=5, category=self.cat)
        self.user = User.objects.create_user(username="u", email="u@example.com", password="pw-123456")
        self.client.force_authenticate(self.user)

    def test_get_creates_empty_cart(self):
        res = self.client.get("/api/cart/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["items"], [])
        self.assertEqual(res.data["total"], "0.00")

    def test_add_then_increment(self):
        self.client.post("/api/cart/items/", {"product": self.p.id, "quantity": 2}, format="json")
        res = self.client.post("/api/cart/items/", {"product": self.p.id, "quantity": 1}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(res.data["items"]), 1)
        self.assertEqual(res.data["items"][0]["quantity"], 3)
        self.assertEqual(res.data["total"], "120.00")

    def test_add_caps_at_stock(self):
        res = self.client.post("/api/cart/items/", {"product": self.p.id, "quantity": 99}, format="json")
        self.assertEqual(res.data["items"][0]["quantity"], 5)  # stock

    def test_patch_sets_quantity_and_zero_removes(self):
        self.client.post("/api/cart/items/", {"product": self.p.id, "quantity": 2}, format="json")
        res = self.client.patch(f"/api/cart/items/{self.p.id}/", {"quantity": 4}, format="json")
        self.assertEqual(res.data["items"][0]["quantity"], 4)
        res = self.client.patch(f"/api/cart/items/{self.p.id}/", {"quantity": 0}, format="json")
        self.assertEqual(res.data["items"], [])

    def test_delete_item_and_clear(self):
        self.client.post("/api/cart/items/", {"product": self.p.id, "quantity": 2}, format="json")
        res = self.client.delete(f"/api/cart/items/{self.p.id}/")
        self.assertEqual(res.data["items"], [])
        # clear on an empty cart is a no-op 200
        res = self.client.delete("/api/cart/")
        self.assertEqual(res.status_code, 200)

    def test_merge_sums_and_caps(self):
        self.client.post("/api/cart/items/", {"product": self.p.id, "quantity": 2}, format="json")
        res = self.client.post("/api/cart/merge/", {"items": [{"product": self.p.id, "quantity": 2}]}, format="json")
        self.assertEqual(res.data["items"][0]["quantity"], 4)  # 2 + 2
        res = self.client.post("/api/cart/merge/", {"items": [{"product": self.p.id, "quantity": 10}]}, format="json")
        self.assertEqual(res.data["items"][0]["quantity"], 5)  # capped at stock

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/cart/").status_code, 401)

    def test_users_have_separate_carts(self):
        self.client.post("/api/cart/items/", {"product": self.p.id, "quantity": 2}, format="json")
        other = User.objects.create_user(username="o", email="o@example.com", password="pw-123456")
        self.client.force_authenticate(other)
        res = self.client.get("/api/cart/")
        self.assertEqual(res.data["items"], [])


class CartVariantTests(APITestCase):
    def setUp(self):
        from products.models import ProductVariant
        self.cat = Category.objects.create(name="Apparel")
        self.tee = Product.objects.create(
            name="Tee", price=Decimal("20.00"), stock=0, category=self.cat
        )
        self.small = ProductVariant.objects.create(
            product=self.tee, options={"Size": "S"}, sku="TEE-S", stock=5
        )
        self.large = ProductVariant.objects.create(
            product=self.tee, options={"Size": "L"}, sku="TEE-L", stock=3,
            price=Decimal("26.00"),
        )
        self.user = User.objects.create_user(
            username="u", email="u@example.com", password="pw-123456"
        )
        self.client.force_authenticate(self.user)

    def test_add_variant_line(self):
        res = self.client.post(
            "/api/cart/items/", {"product": self.tee.id, "variant": self.small.id, "quantity": 2},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        line = res.data["items"][0]
        self.assertEqual(line["variant"]["sku"], "TEE-S")
        self.assertEqual(line["quantity"], 2)

    def test_two_variants_are_separate_lines(self):
        self.client.post("/api/cart/items/", {"product": self.tee.id, "variant": self.small.id, "quantity": 1}, format="json")
        res = self.client.post("/api/cart/items/", {"product": self.tee.id, "variant": self.large.id, "quantity": 1}, format="json")
        self.assertEqual(len(res.data["items"]), 2)

    def test_total_uses_variant_price(self):
        self.client.post("/api/cart/items/", {"product": self.tee.id, "variant": self.large.id, "quantity": 2}, format="json")
        res = self.client.get("/api/cart/")
        self.assertEqual(res.data["total"], "52.00")  # 26 * 2

    def test_add_capped_at_variant_stock(self):
        res = self.client.post("/api/cart/items/", {"product": self.tee.id, "variant": self.large.id, "quantity": 99}, format="json")
        self.assertEqual(res.data["items"][0]["quantity"], 3)  # capped at variant stock

    def test_variant_product_rejects_variantless_add(self):
        res = self.client.post("/api/cart/items/", {"product": self.tee.id, "quantity": 1}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_delete_specific_variant_line(self):
        self.client.post("/api/cart/items/", {"product": self.tee.id, "variant": self.small.id, "quantity": 1}, format="json")
        self.client.post("/api/cart/items/", {"product": self.tee.id, "variant": self.large.id, "quantity": 1}, format="json")
        res = self.client.delete(f"/api/cart/items/{self.tee.id}/?variant={self.small.id}")
        skus = [i["variant"]["sku"] for i in res.data["items"]]
        self.assertEqual(skus, ["TEE-L"])
