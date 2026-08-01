from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    full_slug = models.CharField(max_length=512, unique=True, blank=True)
    level = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if self.parent:
            self.full_slug = f"{self.parent.full_slug}/{self.slug}"
            self.level = self.parent.level + 1
        else:
            self.full_slug = self.slug
            self.level = 0
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    stock = models.PositiveIntegerField(default=0)
    image_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    specifications = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["price"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["is_featured"]),
            models.Index(fields=["stock"]),
            models.Index(fields=["category", "is_active", "-created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def is_on_sale(self) -> bool:
        return self.compare_at_price is not None and self.compare_at_price > self.price

    @property
    def discount_percent(self) -> int:
        if not self.is_on_sale:
            return 0
        return int(round((1 - (float(self.price) / float(self.compare_at_price))) * 100))


class ProductVariant(models.Model):
    """An optional purchasable variation of a product (e.g. Size L / Blue).

    Additive: a product with none is bought directly; one with variants sells
    through them, each with its own stock and optional price override.
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    # {"Size": "L", "Color": "Blue"} — order preserved for display.
    options = models.JSONField(default=dict)
    sku = models.CharField(max_length=64, unique=True)
    stock = models.PositiveIntegerField(default=0)
    # null → inherit product.price; set → this variant costs a different amount.
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            # One variant per option combination within a product.
            models.UniqueConstraint(
                fields=["product", "options"], name="uniq_variant_options_per_product"
            ),
        ]
        indexes = [
            models.Index(fields=["product", "is_active"], name="products_pr_product_var_idx"),
        ]

    @property
    def effective_price(self):
        return self.price if self.price is not None else self.product.price

    @property
    def label(self) -> str:
        # "Size: L / Color: Blue" — a stable human name for snapshots and admin.
        return " / ".join(f"{k}: {v}" for k, v in self.options.items())

    def __str__(self):
        return f"{self.product.name} ({self.label or self.sku})"


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    url = models.URLField(max_length=500)
    alt = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.product.name} image #{self.sort_order}"


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="reviews",
    )
    # Snapshot at write time so the review survives account deletion / rename.
    author_name = models.CharField(max_length=120, blank=True)
    rating = models.PositiveSmallIntegerField()  # 1-5
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    # Snapshot at write time; frozen — a later refund shouldn't retract the badge.
    verified_purchase = models.BooleanField(default=False)
    # Denormalized ReviewVote count so listing never needs a per-row aggregate.
    helpful_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "user"],
                name="uniq_review_per_user_product",
                condition=Q(user__isnull=False),
            ),
            models.CheckConstraint(
                check=Q(rating__gte=1) & Q(rating__lte=5),
                name="review_rating_1_to_5",
            ),
        ]
        indexes = [
            models.Index(fields=["product", "-created_at"]),
            # Backs the "most helpful first" ordering on the reviews list.
            models.Index(
                fields=["product", "-helpful_count"],
                name="review_product_helpful_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.author_name and self.user_id:
            self.author_name = self.user.get_full_name() or self.user.username
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Review {self.rating} on {self.product_id} by {self.author_name or 'anon'}"


class ReviewImage(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="reviews/")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"Image #{self.sort_order} on review {self.review_id}"


class ReviewVote(models.Model):
    """One 'helpful' vote by one user on one review."""

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_votes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["review", "user"], name="uniq_vote_per_user_review"
            ),
        ]

    def __str__(self):
        return f"Helpful vote on review {self.review_id} by {self.user_id}"
