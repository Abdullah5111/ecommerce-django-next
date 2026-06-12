from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from products.models import Category, Product


class Coupon(models.Model):
    class Kind(models.TextChoices):
        PERCENT = "percent", "Percent off"
        FIXED = "fixed", "Fixed amount off"
        FREE_SHIPPING = "free_shipping", "Free shipping"
        BOGO = "bogo", "Buy X get Y"

    code = models.CharField(max_length=40, unique=True)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="percent: 0-100 | fixed: $ off | bogo: % off the free items (100 = free)",
    )
    min_subtotal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    max_redemptions = models.PositiveIntegerField(null=True, blank=True)
    per_user_limit = models.PositiveIntegerField(null=True, blank=True)
    categories = models.ManyToManyField(Category, blank=True, related_name="coupons")
    products = models.ManyToManyField(Product, blank=True, related_name="coupons")
    buy_quantity = models.PositiveSmallIntegerField(null=True, blank=True)
    get_quantity = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def save(self, *args, **kwargs):
        self.code = self.code.upper().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code

    def eligible_items(self, items):
        """items: list of (product, quantity). Returns the in-scope subset.

        Empty product+category scope means the whole catalog is eligible.
        A category in scope also matches its descendants (by full_slug).
        """
        product_ids = set(self.products.values_list("id", flat=True))
        cats = list(self.categories.all())
        if not product_ids and not cats:
            return list(items)
        cat_ids = set()
        if cats:
            q = Q()
            for c in cats:
                q |= Q(full_slug=c.full_slug) | Q(full_slug__startswith=f"{c.full_slug}/")
            cat_ids = set(Category.objects.filter(q).values_list("id", flat=True))
        return [
            (p, qty)
            for (p, qty) in items
            if p.id in product_ids or p.category_id in cat_ids
        ]

    def validate_for(self, user, items, subtotal):
        """Return the first failing reason as a string, or None if valid."""
        now = timezone.now()
        if not self.is_active:
            return "This coupon is not active."
        if self.starts_at and now < self.starts_at:
            return "This coupon is not yet valid."
        if self.expires_at and now > self.expires_at:
            return "This coupon has expired."
        if self.min_subtotal is not None and subtotal < self.min_subtotal:
            return f"Spend at least ${self.min_subtotal} to use this coupon."
        if self.max_redemptions is not None and self.redemptions.count() >= self.max_redemptions:
            return "This coupon has reached its redemption limit."
        if user is not None and self.per_user_limit is not None:
            if self.redemptions.filter(user=user).count() >= self.per_user_limit:
                return "You have already used this coupon."
        if not self.eligible_items(items):
            return "This coupon does not apply to the items in your cart."
        return None


class CouponRedemption(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="redemptions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    order = models.OneToOneField(
        "orders.Order", on_delete=models.CASCADE, related_name="redemption"
    )
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.coupon.code} → order #{self.order_id}"
