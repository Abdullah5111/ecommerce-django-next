import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from cart.models import Cart, CartItem
from orders.models import Order, OrderItem
from products.models import Category, Product, Review, ReviewImage, ReviewVote
from wishlist.models import WishlistItem

User = get_user_model()

# Smallest valid GIF — enough for ImageField to accept the upload.
ONE_PX_GIF = (
    b"GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff,"
    b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


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


class VerifiedPurchaseTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.widget = Product.objects.create(
            name="Widget", price=Decimal("10"), stock=100, category=self.cat
        )
        self.user = User.objects.create_user(
            username="u", email="u@example.com", password="pw-123456"
        )
        self.client.force_authenticate(self.user)

    def _order(self, status):
        order = Order.objects.create(
            user=self.user, shipping_address="x", status=status
        )
        OrderItem.objects.create(
            order=order, product=self.widget, quantity=1, unit_price=self.widget.price
        )

    def _post_review(self):
        return self.client.post(
            f"/api/products/{self.widget.slug}/reviews/", {"rating": 5}
        )

    def test_flag_set_when_user_bought_the_product(self):
        self._order(Order.Status.DELIVERED)
        res = self._post_review()
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data["verified_purchase"])

    def test_flag_unset_without_a_purchase(self):
        res = self._post_review()
        self.assertEqual(res.status_code, 201)
        self.assertFalse(res.data["verified_purchase"])

    def test_pending_and_cancelled_orders_do_not_verify(self):
        self._order(Order.Status.PENDING)
        self._order(Order.Status.CANCELLED)
        res = self._post_review()
        self.assertFalse(res.data["verified_purchase"])

    def test_another_users_purchase_does_not_verify(self):
        buyer = User.objects.create_user(username="buyer", password="pw-123456")
        order = Order.objects.create(
            user=buyer, shipping_address="x", status=Order.Status.DELIVERED
        )
        OrderItem.objects.create(
            order=order, product=self.widget, quantity=1, unit_price=self.widget.price
        )
        res = self._post_review()
        self.assertFalse(res.data["verified_purchase"])

    def test_badge_is_frozen_at_write_time(self):
        # Cancelling later would fail a live recompute (cancelled is not a sold
        # status) — the snapshot must still report the purchase as verified.
        self._order(Order.Status.DELIVERED)
        self._post_review()
        Order.objects.filter(user=self.user).update(status=Order.Status.CANCELLED)
        res = self.client.get(f"/api/products/{self.widget.slug}/reviews/")
        self.assertTrue(res.data["results"][0]["verified_purchase"])


class HelpfulVoteTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.widget = Product.objects.create(
            name="Widget", price=Decimal("10"), stock=100, category=self.cat
        )
        self.author = User.objects.create_user(username="author", password="pw-123456")
        self.voter = User.objects.create_user(username="voter", password="pw-123456")
        self.review = Review.objects.create(
            product=self.widget, user=self.author, rating=5, body="Great"
        )

    def test_vote_requires_auth(self):
        res = self.client.post(f"/api/reviews/{self.review.id}/helpful/")
        self.assertEqual(res.status_code, 401)

    def test_vote_increments_count(self):
        self.client.force_authenticate(self.voter)
        res = self.client.post(f"/api/reviews/{self.review.id}/helpful/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["helpful_count"], 1)
        self.assertTrue(res.data["helpful_by_me"])

    def test_voting_twice_is_idempotent(self):
        self.client.force_authenticate(self.voter)
        self.client.post(f"/api/reviews/{self.review.id}/helpful/")
        res = self.client.post(f"/api/reviews/{self.review.id}/helpful/")
        self.assertEqual(res.data["helpful_count"], 1)
        self.assertEqual(ReviewVote.objects.filter(review=self.review).count(), 1)

    def test_unvote_decrements(self):
        self.client.force_authenticate(self.voter)
        self.client.post(f"/api/reviews/{self.review.id}/helpful/")
        res = self.client.delete(f"/api/reviews/{self.review.id}/helpful/")
        self.assertEqual(res.data["helpful_count"], 0)
        self.assertFalse(res.data["helpful_by_me"])

    def test_unvote_never_goes_negative(self):
        self.client.force_authenticate(self.voter)
        res = self.client.delete(f"/api/reviews/{self.review.id}/helpful/")
        self.assertEqual(res.data["helpful_count"], 0)

    def test_cannot_vote_on_own_review(self):
        self.client.force_authenticate(self.author)
        res = self.client.post(f"/api/reviews/{self.review.id}/helpful/")
        self.assertEqual(res.status_code, 400)
        self.review.refresh_from_db()
        self.assertEqual(self.review.helpful_count, 0)

    def test_helpful_by_me_is_per_viewer(self):
        self.client.force_authenticate(self.voter)
        self.client.post(f"/api/reviews/{self.review.id}/helpful/")

        res = self.client.get(f"/api/products/{self.widget.slug}/reviews/")
        self.assertTrue(res.data["results"][0]["helpful_by_me"])

        other = User.objects.create_user(username="other", password="pw-123456")
        self.client.force_authenticate(other)
        res = self.client.get(f"/api/products/{self.widget.slug}/reviews/")
        self.assertFalse(res.data["results"][0]["helpful_by_me"])

    def test_guest_sees_false_helpful_by_me(self):
        res = self.client.get(f"/api/products/{self.widget.slug}/reviews/")
        self.assertFalse(res.data["results"][0]["helpful_by_me"])

    def test_is_mine_marks_the_viewers_own_review(self):
        self.client.force_authenticate(self.author)
        res = self.client.get(f"/api/products/{self.widget.slug}/reviews/")
        self.assertTrue(res.data["results"][0]["is_mine"])

        self.client.force_authenticate(self.voter)
        res = self.client.get(f"/api/products/{self.widget.slug}/reviews/")
        self.assertFalse(res.data["results"][0]["is_mine"])

    def test_guest_sees_false_is_mine(self):
        res = self.client.get(f"/api/products/{self.widget.slug}/reviews/")
        self.assertFalse(res.data["results"][0]["is_mine"])

    def test_count_survives_voter_deletion(self):
        # The vote rows cascade when the user goes; a hand-maintained counter
        # would stay inflated forever, so this is the drift regression.
        self.client.force_authenticate(self.voter)
        self.client.post(f"/api/reviews/{self.review.id}/helpful/")
        self.review.refresh_from_db()
        self.assertEqual(self.review.helpful_count, 1)

        self.voter.delete()
        self.review.refresh_from_db()
        self.assertEqual(self.review.helpful_count, 0)

    def test_count_tracks_votes_deleted_outside_the_endpoint(self):
        self.client.force_authenticate(self.voter)
        self.client.post(f"/api/reviews/{self.review.id}/helpful/")

        ReviewVote.objects.filter(review=self.review).delete()
        self.review.refresh_from_db()
        self.assertEqual(self.review.helpful_count, 0)

    def test_count_tracks_votes_created_outside_the_endpoint(self):
        other = User.objects.create_user(username="direct", password="pw-123456")
        ReviewVote.objects.create(review=self.review, user=other)
        self.review.refresh_from_db()
        self.assertEqual(self.review.helpful_count, 1)

    def test_deleting_a_review_with_votes_is_clean(self):
        self.client.force_authenticate(self.voter)
        self.client.post(f"/api/reviews/{self.review.id}/helpful/")
        # Votes cascade; the recompute must not blow up on the gone review.
        self.review.delete()
        self.assertEqual(ReviewVote.objects.count(), 0)

    def test_ordering_by_helpful(self):
        popular = Review.objects.create(
            product=self.widget, user=self.voter, rating=4, body="Also good"
        )
        self.client.force_authenticate(self.author)
        self.client.post(f"/api/reviews/{popular.id}/helpful/")

        res = self.client.get(
            f"/api/products/{self.widget.slug}/reviews/?ordering=helpful"
        )
        self.assertEqual(res.data["results"][0]["id"], popular.id)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ReviewImageTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        from django.conf import settings

        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.widget = Product.objects.create(
            name="Widget", price=Decimal("10"), stock=100, category=self.cat
        )
        self.user = User.objects.create_user(username="u", password="pw-123456")
        self.client.force_authenticate(self.user)

    def _gif(self, name="p.gif"):
        return SimpleUploadedFile(name, ONE_PX_GIF, content_type="image/gif")

    def test_review_photos_are_attached_and_returned(self):
        res = self.client.post(
            f"/api/products/{self.widget.slug}/reviews/",
            {"rating": 5, "images": [self._gif("a.gif"), self._gif("b.gif")]},
            format="multipart",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(res.data["images"]), 2)
        self.assertEqual(ReviewImage.objects.count(), 2)
        self.assertTrue(res.data["images"][0]["image"].startswith("http"))

    def test_review_without_photos_still_works(self):
        res = self.client.post(
            f"/api/products/{self.widget.slug}/reviews/", {"rating": 4}
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["images"], [])

    def test_too_many_photos_rejected(self):
        res = self.client.post(
            f"/api/products/{self.widget.slug}/reviews/",
            {"rating": 5, "images": [self._gif(f"{i}.gif") for i in range(6)]},
            format="multipart",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Review.objects.count(), 0)  # nothing partially written

    def test_non_image_file_rejected(self):
        bad = SimpleUploadedFile(
            "payload.png", b"<html><script>alert(1)</script></html>",
            content_type="image/png",
        )
        res = self.client.post(
            f"/api/products/{self.widget.slug}/reviews/",
            {"rating": 5, "images": [bad]},
            format="multipart",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Review.objects.count(), 0)
        self.assertEqual(ReviewImage.objects.count(), 0)

    def test_disallowed_extension_rejected(self):
        # Real image bytes under an .svg name: Pillow would be satisfied, but
        # MEDIA would serve it as image/svg+xml from our own origin, where an
        # embedded <script> executes.
        sneaky = SimpleUploadedFile(
            "x.svg", ONE_PX_GIF, content_type="image/svg+xml"
        )
        res = self.client.post(
            f"/api/products/{self.widget.slug}/reviews/",
            {"rating": 5, "images": [sneaky]},
            format="multipart",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(ReviewImage.objects.count(), 0)

    def test_oversized_photo_rejected(self):
        huge = SimpleUploadedFile(
            "big.gif", ONE_PX_GIF + b"\x00" * (5 * 1024 * 1024),
            content_type="image/gif",
        )
        res = self.client.post(
            f"/api/products/{self.widget.slug}/reviews/",
            {"rating": 5, "images": [huge]},
            format="multipart",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Review.objects.count(), 0)

    def test_one_bad_photo_rejects_the_whole_review(self):
        bad = SimpleUploadedFile("nope.png", b"still not an image")
        res = self.client.post(
            f"/api/products/{self.widget.slug}/reviews/",
            {"rating": 5, "images": [self._gif("ok.gif"), bad]},
            format="multipart",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Review.objects.count(), 0)
        self.assertEqual(ReviewImage.objects.count(), 0)
