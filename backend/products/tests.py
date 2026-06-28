from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from cart.models import Cart, CartItem
from orders.models import Order, OrderItem
from products.models import Category, Product
from wishlist.models import WishlistItem

User = get_user_model()


class SoldCountTests(APITestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # bestsellers caches its response; isolate from other tests
        self.cat = Category.objects.create(name="Gear")
        self.widget = Product.objects.create(
            name="Widget", price=Decimal("10"), stock=100, category=self.cat
        )
        self.user = User.objects.create_user(
            username="u", email="u@example.com", password="pw-123456"
        )

    def _sale(self, status, qty):
        order = Order.objects.create(user=self.user, shipping_address="x", status=status)
        OrderItem.objects.create(
            order=order, product=self.widget, quantity=qty, unit_price=self.widget.price
        )

    def _sold_count(self):
        res = self.client.get(f"/api/products/{self.widget.slug}/")
        self.assertEqual(res.status_code, 200)
        return res.data["sold_count"]

    def test_zero_when_no_sales(self):
        self.assertEqual(self._sold_count(), 0)

    def test_counts_paid_shipped_delivered_and_refunded(self):
        self._sale(Order.Status.PAID, 2)
        self._sale(Order.Status.SHIPPED, 3)
        self._sale(Order.Status.DELIVERED, 1)
        self._sale(Order.Status.PARTIALLY_REFUNDED, 1)
        self.assertEqual(self._sold_count(), 7)

    def test_excludes_pending_and_cancelled(self):
        self._sale(Order.Status.PAID, 4)
        self._sale(Order.Status.PENDING, 5)
        self._sale(Order.Status.CANCELLED, 6)
        self.assertEqual(self._sold_count(), 4)

    def test_bestsellers_ranks_by_units_sold(self):
        hot = Product.objects.create(
            name="Hot", price=Decimal("10"), stock=100, category=self.cat
        )
        order = Order.objects.create(
            user=self.user, shipping_address="x", status=Order.Status.DELIVERED
        )
        OrderItem.objects.create(order=order, product=hot, quantity=50, unit_price=hot.price)
        res = self.client.get("/api/products/bestsellers/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data[0]["id"], hot.id)


class RecommendedTests(APITestCase):
    def setUp(self):
        self.electronics = Category.objects.create(name="Electronics")
        self.books = Category.objects.create(name="Books")
        self.phone = Product.objects.create(
            name="Phone", price=Decimal("500"), stock=5, category=self.electronics
        )
        self.headphones = Product.objects.create(
            name="Headphones", price=Decimal("100"), stock=5, category=self.electronics,
            rating_avg=Decimal("4.50"), rating_count=10,
        )
        self.novel = Product.objects.create(
            name="Novel", price=Decimal("15"), stock=5, category=self.books
        )
        self.novel2 = Product.objects.create(
            name="Novel 2", price=Decimal("18"), stock=5, category=self.books
        )
        self.user = User.objects.create_user(
            username="u", email="u@example.com", password="pw-123456"
        )

    def test_guest_gets_fallback(self):
        res = self.client.get("/api/products/recommended/")
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.data), 1)

    def test_recommendations_from_purchase_history(self):
        order = Order.objects.create(user=self.user, shipping_address="x")
        OrderItem.objects.create(order=order, product=self.phone, quantity=1, unit_price=Decimal("500"))
        self.client.force_authenticate(self.user)
        res = self.client.get("/api/products/recommended/")
        ids = [p["id"] for p in res.data]
        self.assertIn(self.headphones.id, ids)   # same category as the purchase
        self.assertNotIn(self.phone.id, ids)     # already purchased — excluded
        self.assertNotIn(self.novel.id, ids)     # unrelated category

    def test_wishlist_drives_recommendations(self):
        WishlistItem.objects.create(user=self.user, product=self.novel)
        self.client.force_authenticate(self.user)
        res = self.client.get("/api/products/recommended/")
        ids = [p["id"] for p in res.data]
        self.assertIn(self.novel2.id, ids)       # books category from wishlist affinity
        self.assertNotIn(self.headphones.id, ids)  # electronics not in affinity

    def test_cart_drives_recommendations(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.phone, quantity=1)
        self.client.force_authenticate(self.user)
        res = self.client.get("/api/products/recommended/")
        ids = [p["id"] for p in res.data]
        self.assertIn(self.headphones.id, ids)   # electronics affinity from cart

    def test_new_user_gets_fallback(self):
        self.client.force_authenticate(self.user)
        res = self.client.get("/api/products/recommended/")
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.data), 1)  # no signals → fallback list
