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
    # Snapshot the reviewer display name at write time so the review survives
    # account deletion / username change.
    author_name = models.CharField(max_length=120, blank=True)
    rating = models.PositiveSmallIntegerField()  # 1-5
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
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
        ]

    def save(self, *args, **kwargs):
        if not self.author_name and self.user_id:
            self.author_name = self.user.get_full_name() or self.user.username
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Review {self.rating} on {self.product_id} by {self.author_name or 'anon'}"
