import os
import shutil
import tempfile
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from cart.models import Cart, CartItem
from orders.models import Order, OrderItem
from products.models import (
    Category, Product, ProductImage, ProductVariant, Review, ReviewImage, ReviewVote,
)
from products.throttling import ReviewWriteThrottle
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


class SearchSuggestTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.blue = Product.objects.create(
            name="Blue Running Shoes", price=Decimal("50"), stock=5,
            category=self.cat, image_url="http://img/blue.jpg",
        )
        self.red = Product.objects.create(
            name="Red Running Socks", price=Decimal("8"), stock=5, category=self.cat
        )
        self.hidden = Product.objects.create(
            name="Running Hat (discontinued)", price=Decimal("9"), stock=0,
            category=self.cat, is_active=False,
        )

    def test_matches_by_substring_case_insensitive(self):
        res = self.client.get("/api/products/suggest/?q=running")
        self.assertEqual(res.status_code, 200)
        names = {r["name"] for r in res.data}
        self.assertEqual(names, {"Blue Running Shoes", "Red Running Socks"})

    def test_excludes_inactive_products(self):
        res = self.client.get("/api/products/suggest/?q=hat")
        self.assertEqual(res.data, [])

    def test_short_query_returns_empty_without_hitting_db(self):
        res = self.client.get("/api/products/suggest/?q=r")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, [])

    def test_missing_query_returns_empty(self):
        res = self.client.get("/api/products/suggest/")
        self.assertEqual(res.data, [])

    def test_payload_is_lean_with_string_price(self):
        res = self.client.get("/api/products/suggest/?q=blue")
        self.assertEqual(len(res.data), 1)
        row = res.data[0]
        self.assertEqual(
            set(row.keys()), {"id", "name", "slug", "price", "image_url"}
        )
        self.assertEqual(row["price"], "50.00")
        self.assertEqual(row["image_url"], "http://img/blue.jpg")

    def test_prefix_matches_rank_before_mid_word(self):
        # "Alpha Shoe" is alphabetically first, but "Shoe Rack" starts with the
        # query and must therefore win the top slot.
        Product.objects.create(
            name="Alpha Shoe", price=Decimal("1"), stock=1, category=self.cat
        )
        Product.objects.create(
            name="Shoe Rack", price=Decimal("1"), stock=1, category=self.cat
        )
        res = self.client.get("/api/products/suggest/?q=shoe")
        self.assertEqual(res.data[0]["name"], "Shoe Rack")

    def test_capped_at_eight_results(self):
        for i in range(10):
            Product.objects.create(
                name=f"Widget {i:02d}", price=Decimal("1"), stock=1, category=self.cat
            )
        res = self.client.get("/api/products/suggest/?q=widget")
        self.assertEqual(len(res.data), 8)

    def test_thumbnail_falls_back_to_gallery_image(self):
        p = Product.objects.create(
            name="Galleried Widget", price=Decimal("1"), stock=1,
            category=self.cat, image_url="",
        )
        ProductImage.objects.create(product=p, url="http://img/gallery.jpg", sort_order=0)
        res = self.client.get("/api/products/suggest/?q=galleried")
        self.assertEqual(res.data[0]["image_url"], "http://img/gallery.jpg")


class CategoryCycleGuardTests(APITestCase):
    def test_cannot_parent_to_self(self):
        a = Category.objects.create(name="A")
        a.parent = a
        with self.assertRaises(ValidationError):
            a.save()

    def test_cannot_parent_to_own_descendant(self):
        a = Category.objects.create(name="A")
        b = Category.objects.create(name="B", parent=a)
        a.parent = b
        with self.assertRaises(ValidationError):
            a.save()


class CategorySlugCascadeTests(APITestCase):
    def test_rename_cascades_full_slug_to_descendants(self):
        a = Category.objects.create(name="Alpha")
        b = Category.objects.create(name="Beta", parent=a)
        c = Category.objects.create(name="Gamma", parent=b)
        self.assertEqual(c.full_slug, "alpha/beta/gamma")

        a.slug = "alpha2"
        a.save()
        b.refresh_from_db()
        c.refresh_from_db()
        self.assertEqual(b.full_slug, "alpha2/beta")
        self.assertEqual(c.full_slug, "alpha2/beta/gamma")
        self.assertEqual(c.level, 2)

    def test_reparent_updates_slug_and_level(self):
        a = Category.objects.create(name="A")
        x = Category.objects.create(name="X")
        b = Category.objects.create(name="B", parent=a)
        self.assertEqual(b.full_slug, "a/b")

        b.parent = x
        b.save()
        b.refresh_from_db()
        self.assertEqual(b.full_slug, "x/b")
        self.assertEqual(b.level, 1)


class CategoryAncestorsTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.a = Category.objects.create(name="Alpha")
        self.b = Category.objects.create(name="Beta", parent=self.a)
        self.c = Category.objects.create(name="Gamma", parent=self.b)

    def test_ancestors_root_to_parent(self):
        res = self.client.get("/api/categories/by-path/?path=alpha/beta/gamma")
        self.assertEqual(res.status_code, 200)
        self.assertEqual([a["slug"] for a in res.data["ancestors"]], ["alpha", "beta"])

    def test_root_has_no_ancestors(self):
        res = self.client.get("/api/categories/by-path/?path=alpha")
        self.assertEqual(res.data["ancestors"], [])


class RelatedProductsTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.root = Category.objects.create(name="Electronics")
        self.phones = Category.objects.create(name="Phones", parent=self.root)
        self.laptops = Category.objects.create(name="Laptops", parent=self.root)
        self.phone = Product.objects.create(
            name="Phone A", price=Decimal("5"), stock=1, category=self.phones
        )
        # Sibling category product; only candidate to fill the sparse phone rail.
        self.laptop = Product.objects.create(
            name="Laptop A", price=Decimal("5"), stock=1,
            category=self.laptops, rating_avg=Decimal("5"),
        )

    def test_widens_to_branch_when_category_sparse(self):
        res = self.client.get(f"/api/products/{self.phone.slug}/related/")
        self.assertEqual(res.status_code, 200)
        ids = {p["id"] for p in res.data}
        self.assertIn(self.laptop.id, ids)


class CatalogCacheInvalidationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.cat = Category.objects.create(name="C")
        self.p = Product.objects.create(
            name="Feat", price=Decimal("5"), stock=1, category=self.cat, is_featured=True
        )

    def test_featured_refreshes_when_product_deactivated(self):
        res1 = self.client.get("/api/products/featured/")
        self.assertEqual(len(res1.data), 1)

        self.p.is_active = False
        self.p.save()  # signal bumps the cache version

        res2 = self.client.get("/api/products/featured/")
        self.assertEqual(len(res2.data), 0)


class CategoryTreeTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.a = Category.objects.create(name="Apparel")
        self.men = Category.objects.create(name="Men", parent=self.a)
        self.shirts = Category.objects.create(name="Shirts", parent=self.men)
        self.b = Category.objects.create(name="Books")

    def test_tree_is_nested(self):
        res = self.client.get("/api/categories/tree/")
        self.assertEqual(res.status_code, 200)
        roots = {c["name"]: c for c in res.data}
        self.assertEqual(set(roots), {"Apparel", "Books"})
        apparel = roots["Apparel"]
        self.assertEqual([c["name"] for c in apparel["children"]], ["Men"])
        self.assertEqual(
            [c["name"] for c in apparel["children"][0]["children"]], ["Shirts"]
        )
        self.assertEqual(roots["Books"]["children"], [])


class FeaturedSortTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        # Featured created first (older); the plain product created after is newer.
        self.feat = Product.objects.create(
            name="Featured One", price=Decimal("10"), stock=5,
            category=self.cat, is_featured=True,
        )
        self.newer = Product.objects.create(
            name="Newer Plain", price=Decimal("10"), stock=5, category=self.cat,
        )

    def test_default_order_puts_featured_first(self):
        res = self.client.get("/api/products/")
        self.assertEqual(res.status_code, 200)
        names = [p["name"] for p in res.data["results"]]
        self.assertEqual(names[0], "Featured One")

    def test_newest_sort_overrides_featured(self):
        res = self.client.get("/api/products/?ordering=-created_at")
        names = [p["name"] for p in res.data["results"]]
        self.assertEqual(names[0], "Newer Plain")


class SearchTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Lighting")
        self.lamp = Product.objects.create(
            name="Aurora Lamp", description="a bright bedside light",
            price=Decimal("30"), stock=5, category=self.cat,
        )
        self.mug = Product.objects.create(
            name="Coffee Mug", description="ceramic cup",
            price=Decimal("8"), stock=5, category=self.cat,
        )

    def _names(self, q):
        res = self.client.get(f"/api/products/?search={q}")
        self.assertEqual(res.status_code, 200)
        return {p["name"] for p in res.data["results"]}

    def test_matches_by_name(self):
        self.assertEqual(self._names("aurora"), {"Aurora Lamp"})

    def test_matches_by_description(self):
        # Guards against reintroducing SearchFilter-only search (which would still
        # work here); the point is that get_queryset owns description matching.
        self.assertEqual(self._names("bedside"), {"Aurora Lamp"})

    def test_no_match_returns_empty(self):
        self.assertEqual(self._names("nonexistentxyz"), set())


class SoldCountDenormTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.cat = Category.objects.create(name="Gear")
        self.p = Product.objects.create(
            name="Gizmo", price=Decimal("10"), stock=100, category=self.cat
        )
        self.user = User.objects.create_user(
            username="sc", email="sc@example.com", password="pw-123456"
        )

    def test_denormalized_field_tracks_status_changes(self):
        order = Order.objects.create(
            user=self.user, shipping_address="x", status=Order.Status.PENDING
        )
        OrderItem.objects.create(
            order=order, product=self.p, quantity=3, unit_price=self.p.price
        )
        self.p.refresh_from_db()
        self.assertEqual(self.p.sold_count, 0)  # pending doesn't count

        order.status = Order.Status.PAID
        order.save()
        self.p.refresh_from_db()
        self.assertEqual(self.p.sold_count, 3)  # signal recomputed on status change

        order.status = Order.Status.CANCELLED
        order.save()
        self.p.refresh_from_db()
        self.assertEqual(self.p.sold_count, 0)  # left the sold set


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


class RecommendedCancelledOrderTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ru", email="ru@example.com", password="pw-123456"
        )
        self.cat = Category.objects.create(name="Books")
        self.p = Product.objects.create(
            name="P Book", price=Decimal("10"), stock=5, category=self.cat
        )
        self.q = Product.objects.create(
            name="Q Book", price=Decimal("10"), stock=5, category=self.cat
        )
        # Wishlist gives recs a category signal without counting as a purchase.
        WishlistItem.objects.create(user=self.user, product=self.q)

    def test_cancelled_purchase_not_treated_as_owned(self):
        order = Order.objects.create(
            user=self.user, shipping_address="x", status=Order.Status.CANCELLED
        )
        OrderItem.objects.create(
            order=order, product=self.p, quantity=1, unit_price=self.p.price
        )
        self.client.force_authenticate(self.user)
        res = self.client.get("/api/products/recommended/")
        self.assertEqual(res.status_code, 200)
        ids = {p["id"] for p in res.data}
        self.assertIn(self.p.id, ids)


class VerifiedPurchaseTests(APITestCase):
    def setUp(self):
        # Throttle history lives in the cache, which TestCase does not roll
        # back — without this, review POSTs accumulate across tests and later
        # ones start 429ing.
        cache.clear()
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
        buyer = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="pw-123456"
        )
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
        cache.clear()  # vote throttle history persists across tests
        self.cat = Category.objects.create(name="Gear")
        self.widget = Product.objects.create(
            name="Widget", price=Decimal("10"), stock=100, category=self.cat
        )
        self.author = User.objects.create_user(
            username="author", email="author@example.com", password="pw-123456"
        )
        self.voter = User.objects.create_user(
            username="voter", email="voter@example.com", password="pw-123456"
        )
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

        other = User.objects.create_user(
            username="other", email="other@example.com", password="pw-123456"
        )
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
        other = User.objects.create_user(
            username="direct", email="direct@example.com", password="pw-123456"
        )
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


class ReviewThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()
        # Dial the limits down so they're reachable without hammering.
        # override_settings(REST_FRAMEWORK=...) does NOT work here:
        # SimpleRateThrottle.THROTTLE_RATES is bound to the settings dict at
        # class-definition time, so replacing the setting leaves the class
        # pointing at the original dict. Patching the dict itself is what the
        # throttle actually reads.
        rates = patch.dict(
            ReviewWriteThrottle.THROTTLE_RATES,
            {"review-write": "2/hour", "review-vote": "2/hour"},
        )
        rates.start()
        self.addCleanup(rates.stop)
        self.cat = Category.objects.create(name="Gear")
        self.widget = Product.objects.create(
            name="Widget", price=Decimal("10"), stock=100, category=self.cat
        )
        self.author = User.objects.create_user(
            username="author", email="author@example.com", password="pw-123456"
        )
        self.voter = User.objects.create_user(
            username="voter", email="voter@example.com", password="pw-123456"
        )

    def test_public_review_listing_is_never_throttled(self):
        # The GET shares a route with the throttled POST; browsing reviews must
        # not be rate-limited.
        for _ in range(10):
            res = self.client.get(f"/api/products/{self.widget.slug}/reviews/")
            self.assertEqual(res.status_code, 200)

    def test_posting_reviews_is_throttled(self):
        self.client.force_authenticate(self.author)
        url = f"/api/products/{self.widget.slug}/reviews/"
        # Rate is 2/hour. The duplicate-review 400s still consume the budget,
        # because throttling runs before the view body.
        self.client.post(url, {"rating": 5})
        self.client.post(url, {"rating": 4})
        res = self.client.post(url, {"rating": 3})
        self.assertEqual(res.status_code, 429)

    def test_helpful_votes_are_throttled(self):
        review = Review.objects.create(
            product=self.widget, user=self.author, rating=5, body="Great"
        )
        self.client.force_authenticate(self.voter)
        url = f"/api/reviews/{review.id}/helpful/"
        self.client.post(url)
        self.client.delete(url)
        res = self.client.post(url)
        self.assertEqual(res.status_code, 429)

    def test_throttles_are_per_user(self):
        url = f"/api/products/{self.widget.slug}/reviews/"
        self.client.force_authenticate(self.author)
        self.client.post(url, {"rating": 5})
        self.client.post(url, {"rating": 5})
        self.assertEqual(self.client.post(url, {"rating": 5}).status_code, 429)

        # A different user starts with a fresh budget.
        self.client.force_authenticate(self.voter)
        self.assertEqual(self.client.post(url, {"rating": 4}).status_code, 201)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ReviewImageTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        from django.conf import settings

        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        cache.clear()  # review-write throttle history persists across tests
        self.cat = Category.objects.create(name="Gear")
        self.widget = Product.objects.create(
            name="Widget", price=Decimal("10"), stock=100, category=self.cat
        )
        self.user = User.objects.create_user(
            username="u", email="u@example.com", password="pw-123456"
        )
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

    def test_bad_rating_and_bad_image_are_reported_together(self):
        # A request wrong in both ways should surface both errors at once,
        # not make the user fix them one round-trip at a time.
        res = self.client.post(
            f"/api/products/{self.widget.slug}/reviews/",
            {"rating": 9, "images": [SimpleUploadedFile("x.txt", b"nope")]},
            format="multipart",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("rating", res.data)
        self.assertIn("images", res.data)
        self.assertEqual(Review.objects.count(), 0)

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

    def test_file_is_removed_when_the_image_row_is_deleted(self):
        self.client.post(
            f"/api/products/{self.widget.slug}/reviews/",
            {"rating": 5, "images": [self._gif()]},
            format="multipart",
        )
        img = ReviewImage.objects.get()
        path = img.image.path
        self.assertTrue(os.path.exists(path))

        img.delete()
        self.assertFalse(os.path.exists(path))

    def test_files_are_removed_when_the_review_is_deleted(self):
        # The cascade is the case that actually leaks: rows vanish, files stay.
        self.client.post(
            f"/api/products/{self.widget.slug}/reviews/",
            {"rating": 5, "images": [self._gif("a.gif"), self._gif("b.gif")]},
            format="multipart",
        )
        paths = [i.image.path for i in ReviewImage.objects.all()]
        self.assertEqual(len(paths), 2)
        self.assertTrue(all(os.path.exists(p) for p in paths))

        Review.objects.get().delete()
        self.assertEqual(ReviewImage.objects.count(), 0)
        self.assertFalse(any(os.path.exists(p) for p in paths))

    def test_deleting_an_image_whose_file_is_already_gone_is_safe(self):
        self.client.post(
            f"/api/products/{self.widget.slug}/reviews/",
            {"rating": 5, "images": [self._gif()]},
            format="multipart",
        )
        img = ReviewImage.objects.get()
        os.remove(img.image.path)  # simulate out-of-band cleanup
        img.delete()  # must not raise
        self.assertEqual(ReviewImage.objects.count(), 0)

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


class ProductVariantAPITests(APITestCase):
    def setUp(self):
        cache.clear()  # featured/etc. cache their responses
        self.cat = Category.objects.create(name="Apparel")
        self.tshirt = Product.objects.create(
            name="Tee", price=Decimal("20.00"), stock=0, category=self.cat
        )
        self.plain = Product.objects.create(
            name="Mug", price=Decimal("8.00"), stock=5, category=self.cat
        )
        # Two variants: one at product price, one with an override.
        self.small = ProductVariant.objects.create(
            product=self.tshirt, options={"Size": "S"}, sku="TEE-S", stock=3
        )
        self.large = ProductVariant.objects.create(
            product=self.tshirt, options={"Size": "L"}, sku="TEE-L", stock=0,
            price=Decimal("24.00"),
        )

    def test_detail_lists_active_variants(self):
        res = self.client.get(f"/api/products/{self.tshirt.slug}/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["has_variants"])
        skus = {v["sku"] for v in res.data["variants"]}
        self.assertEqual(skus, {"TEE-S", "TEE-L"})

    def test_effective_price_and_in_stock(self):
        res = self.client.get(f"/api/products/{self.tshirt.slug}/")
        by_sku = {v["sku"]: v for v in res.data["variants"]}
        self.assertEqual(by_sku["TEE-S"]["effective_price"], "20.00")  # inherits
        self.assertEqual(by_sku["TEE-L"]["effective_price"], "24.00")  # override
        self.assertTrue(by_sku["TEE-S"]["in_stock"])
        self.assertFalse(by_sku["TEE-L"]["in_stock"])

    def test_price_from_is_cheapest_variant(self):
        res = self.client.get(f"/api/products/{self.tshirt.slug}/")
        self.assertEqual(res.data["price_from"], "20.00")

    def test_inactive_variants_are_hidden(self):
        self.large.is_active = False
        self.large.save(update_fields=["is_active"])
        res = self.client.get(f"/api/products/{self.tshirt.slug}/")
        skus = {v["sku"] for v in res.data["variants"]}
        self.assertEqual(skus, {"TEE-S"})

    def test_product_without_variants_reports_none(self):
        res = self.client.get(f"/api/products/{self.plain.slug}/")
        self.assertFalse(res.data["has_variants"])
        self.assertEqual(res.data["variants"], [])
        self.assertEqual(res.data["price_from"], "8.00")

    def test_list_cards_omit_the_variant_array(self):
        # Cards use the lean serializer; only has_variants/price_from ride along.
        res = self.client.get("/api/products/")
        row = next(r for r in res.data["results"] if r["slug"] == self.tshirt.slug)
        self.assertNotIn("variants", row)
        self.assertTrue(row["has_variants"])
        self.assertEqual(row["price_from"], "20.00")

    def test_duplicate_option_combo_is_rejected(self):
        from django.db import IntegrityError, transaction

        # atomic() so the failed INSERT doesn't taint the outer test transaction.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProductVariant.objects.create(
                    product=self.tshirt, options={"Size": "S"}, sku="TEE-S2", stock=1
                )
