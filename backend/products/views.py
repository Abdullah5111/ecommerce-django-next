import django_filters
from django.core.cache import cache
from django.db import IntegrityError, connection, transaction
from django.db.models import Case, Exists, IntegerField, OuterRef, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .models import Category, Product, Review, ReviewImage, ReviewVote
from .serializers import (
    CategorySerializer,
    CategoryTreeSerializer,
    CategoryDetailSerializer,
    ProductSerializer,
    ProductDetailSerializer,
    ReviewImageUploadSerializer,
    ReviewSerializer,
)
from .throttling import ReviewVoteThrottle, ReviewWriteThrottle

# Cap on photos per review — keeps a single upload from filling the disk.
MAX_REVIEW_IMAGES = 5

# Order statuses that count as a completed sale (an order that was paid and not
# cancelled — cancellation restocks, so it must not count). Used for "X sold".
SOLD_STATUSES = ("paid", "shipped", "delivered", "partially_refunded", "refunded")


def _sold_annotation():
    return Coalesce(
        Sum("orderitem__quantity", filter=Q(orderitem__order__status__in=SOLD_STATUSES)),
        0,
    )


def _has_purchased(user, product) -> bool:
    """Whether `user` has a completed order containing `product`.

    Reuses SOLD_STATUSES so "bought it" means the same thing here as it does
    for the "X sold" badge.
    """
    return product.orderitem_set.filter(
        order__user=user, order__status__in=SOLD_STATUSES
    ).exists()


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"

    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request):
        roots = Category.objects.filter(parent__isnull=True)
        serializer = CategoryTreeSerializer(roots, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="by-path")
    def by_path(self, request):
        path = request.query_params.get("path", "")
        try:
            cat = Category.objects.get(full_slug=path)
        except Category.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        return Response(CategoryDetailSerializer(cat).data)


class ProductFilter(django_filters.FilterSet):
    category__slug = django_filters.CharFilter(
        field_name="category__slug", lookup_expr="exact"
    )
    category_path = django_filters.CharFilter(method="filter_category_path")
    price__gte = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    price__lte = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")

    class Meta:
        model = Product
        fields = ["category__slug", "category_path", "price__gte", "price__lte", "in_stock"]

    def filter_category_path(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(category__full_slug=value)
            | Q(category__full_slug__startswith=value + "/")
        )

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__gt=0)
        return queryset


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.filter(is_active=True).select_related("category")
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"
    filterset_class = ProductFilter
    search_fields = ["name", "description"]
    ordering_fields = ["price", "created_at"]
    # Reviews accept multipart (photo uploads) as well as plain JSON.
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_serializer_class(self):
        # Detail carries the full variant list; list/cards stay lean.
        if self.action == "retrieve":
            return ProductDetailSerializer
        return ProductSerializer

    def get_queryset(self):
        qs = (
            Product.objects.filter(is_active=True)
            .select_related("category")
            # Powers has_variants / price_from (and the detail variant list)
            # without a query per product.
            .prefetch_related("variants")
        )
        # Postgres full-text search path: only when on PG and ?search= is set.
        if connection.vendor == "postgresql":
            q = self.request.query_params.get("search") if hasattr(self, "request") and self.request else None
            if q:
                from django.contrib.postgres.search import (
                    SearchQuery,
                    SearchRank,
                    SearchVector,
                )
                vector = SearchVector("name", "description")
                query = SearchQuery(q)
                qs = (
                    qs.annotate(rank=SearchRank(vector, query))
                    .filter(rank__gt=0)
                    .order_by("-rank")
                )
        return qs.annotate(sold_count=_sold_annotation())

    @action(detail=False, methods=["get"], url_path="featured")
    def featured(self, request):
        cache_key = "products:featured:v1"
        data = cache.get(cache_key)
        if data is None:
            qs = self.get_queryset().filter(is_featured=True).order_by("-created_at")[:12]
            data = self.get_serializer(qs, many=True).data
            cache.set(cache_key, data, timeout=300)
        return Response(data)

    @action(
        detail=False,
        methods=["get"],
        url_path="suggest",
        permission_classes=[permissions.AllowAny],
    )
    def suggest(self, request):
        """Typeahead for the search box: a few lean matches, no heavy joins.

        Deliberately does NOT use the Postgres full-text path `get_queryset`
        takes — typeahead needs substring/prefix hits on partial words, and
        this must also work on the sqlite test/dev fallback. `icontains`
        gives both. Payload is kept minimal (no variants/images/reviews) and
        capped, so it stays cheap on every keystroke.
        """
        q = (request.query_params.get("q") or "").strip()
        if len(q) < 2:
            return Response([])
        rows = (
            Product.objects.filter(is_active=True, name__icontains=q)
            # Rank names that *start* with the query above mid-word matches, so
            # typing "shoe" surfaces "Shoe Rack" before "Blue Shoe"; ties break
            # alphabetically.
            .annotate(
                match_rank=Case(
                    When(name__istartswith=q, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            )
            .order_by("match_rank", "name")
            .values("id", "name", "slug", "price", "image_url")[:8]
        )
        return Response(
            [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "slug": r["slug"],
                    # str() to match the string prices the rest of the API emits.
                    "price": str(r["price"]),
                    "image_url": r["image_url"],
                }
                for r in rows
            ]
        )

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="reviews",
        permission_classes=[permissions.AllowAny],
        # Write-only throttle: the public GET on this route stays unlimited.
        throttle_classes=[ReviewWriteThrottle],
    )
    def reviews(self, request, slug=None):
        product = self.get_object()
        if request.method == "GET":
            qs = product.reviews.all().prefetch_related("images")
            if request.user.is_authenticated:
                # Resolve the viewer's own vote in the same query the list runs.
                qs = qs.annotate(
                    voted_by_me=Exists(
                        ReviewVote.objects.filter(
                            review=OuterRef("pk"), user=request.user
                        )
                    )
                )
            if request.query_params.get("ordering") == "helpful":
                qs = qs.order_by("-helpful_count", "-created_at")
            else:
                qs = qs.order_by("-created_at")
            page = self.paginate_queryset(qs)
            ser = ReviewSerializer(
                page if page is not None else qs,
                many=True,
                context={"request": request},
            )
            return (
                self.get_paginated_response(ser.data)
                if page is not None
                else Response(ser.data)
            )

        # POST — require auth
        if not request.user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=401)

        # Validate the review fields and the photos together, then raise once,
        # so a request that's wrong in both ways (bad rating *and* bad images)
        # reports both at once instead of making the user fix them one per
        # round-trip. Nothing is written until every upload is proven a real,
        # allowed, size-capped image — a rejected photo must not leave a review
        # behind.
        ser = ReviewSerializer(data=request.data, context={"request": request})
        review_ok = ser.is_valid()

        images = request.FILES.getlist("images")
        image_errors = []
        if len(images) > MAX_REVIEW_IMAGES:
            image_errors.append(f"At most {MAX_REVIEW_IMAGES} images per review.")
        else:
            for upload in images:
                img_ser = ReviewImageUploadSerializer(data={"image": upload})
                if not img_ser.is_valid():
                    image_errors.extend(img_ser.errors.get("image", []))

        if not review_ok or image_errors:
            errors = dict(ser.errors)
            if image_errors:
                errors["images"] = image_errors
            raise ValidationError(errors)

        try:
            with transaction.atomic():
                review = ser.save(
                    product=product,
                    user=request.user,
                    verified_purchase=_has_purchased(request.user, product),
                )
                for i, upload in enumerate(images):
                    ReviewImage.objects.create(review=review, image=upload, sort_order=i)
        except IntegrityError:
            return Response(
                {"detail": "You already reviewed this product."}, status=400
            )
        return Response(
            ReviewSerializer(review, context={"request": request}).data, status=201
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="related",
        permission_classes=[permissions.AllowAny],
    )
    def related(self, request, slug=None):
        product = self.get_object()
        cache_key = f"products:related:{product.id}:v1"
        data = cache.get(cache_key)
        if data is None:
            qs = (
                Product.objects.filter(is_active=True, category=product.category)
                .exclude(pk=product.pk)
                .select_related("category")
                .prefetch_related("variants")
                .order_by("-rating_avg", "-created_at")[:8]
            )
            data = ProductSerializer(qs, many=True).data
            cache.set(cache_key, data, timeout=300)
        return Response(data)

    @action(detail=False, methods=["get"], url_path="recommended")
    def recommended(self, request):
        """Content-based recommendations from the signed-in user's signals.

        Affinity categories come from the user's purchases, wishlist, and cart;
        we surface active products from those categories (excluding ones already
        purchased), ranked featured-first then by rating. Guests and new users
        with no signals fall back to top featured/rated products.
        """
        limit = 12
        user = request.user
        if user.is_authenticated:
            # Local imports avoid a circular dependency (orders/cart/wishlist
            # all import products at module load).
            from cart.models import CartItem
            from orders.models import OrderItem
            from wishlist.models import WishlistItem

            owned_ids = set(
                OrderItem.objects.filter(order__user=user).values_list("product_id", flat=True)
            )
            cat_ids = set(
                Product.objects.filter(pk__in=owned_ids).values_list("category_id", flat=True)
            )
            cat_ids |= set(
                WishlistItem.objects.filter(user=user).values_list("product__category_id", flat=True)
            )
            cat_ids |= set(
                CartItem.objects.filter(cart__user=user).values_list("product__category_id", flat=True)
            )
            if cat_ids:
                qs = (
                    Product.objects.filter(is_active=True, category_id__in=cat_ids)
                    .exclude(pk__in=owned_ids)
                    .select_related("category")
                    .prefetch_related("variants")
                    .order_by("-is_featured", "-rating_avg", "-rating_count")[:limit]
                )
                products = list(qs)
                if products:
                    return Response(self.get_serializer(products, many=True).data)

        # Fallback: guests, new users, or no in-category candidates left.
        qs = (
            Product.objects.filter(is_active=True)
            .select_related("category")
            .prefetch_related("variants")
            .order_by("-is_featured", "-rating_avg", "-rating_count")[:limit]
        )
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="bestsellers")
    def bestsellers(self, request):
        cache_key = "products:bestsellers:v1"
        data = cache.get(cache_key)
        if data is None:
            # get_queryset already annotates sold_count for every product.
            qs = self.get_queryset().order_by("-sold_count", "-created_at")[:12]
            data = self.get_serializer(qs, many=True).data
            cache.set(cache_key, data, timeout=300)
        return Response(data)


class ReviewViewSet(viewsets.GenericViewSet):
    """Actions that target a single review by id, independent of its product."""

    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(
        detail=True,
        methods=["post", "delete"],
        url_path="helpful",
        throttle_classes=[ReviewVoteThrottle],
    )
    def helpful(self, request, pk=None):
        review = self.get_object()
        if review.user_id == request.user.id:
            return Response(
                {"detail": "You cannot vote on your own review."}, status=400
            )

        # helpful_count is maintained by the post_save/post_delete receivers on
        # ReviewVote (products/signals.py), the same way Review drives the
        # product's rating fields. Writing the vote row is the whole job here.
        if request.method == "POST":
            ReviewVote.objects.get_or_create(review=review, user=request.user)
            voted = True
        else:
            ReviewVote.objects.filter(review=review, user=request.user).delete()
            voted = False

        review.refresh_from_db(fields=["helpful_count"])
        return Response({"helpful_count": review.helpful_count, "helpful_by_me": voted})
