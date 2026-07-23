from django.conf import settings
from django.db import models
from django.db.models import Q

from products.models import Product, ProductVariant


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart({self.user})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.PositiveSmallIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # NULLs compare distinct in Postgres, so a single unique across
            # (cart, product, variant) would let a product without a variant
            # be added twice. Split it: one line per product when there's no
            # variant, one line per (product, variant) when there is.
            models.UniqueConstraint(
                fields=["cart", "product"],
                condition=Q(variant__isnull=True),
                name="uniq_cart_product_no_variant",
            ),
            models.UniqueConstraint(
                fields=["cart", "product", "variant"],
                condition=Q(variant__isnull=False),
                name="uniq_cart_product_variant",
            ),
        ]
        ordering = ["added_at"]

    def __str__(self):
        return f"{self.quantity}x {self.product_id}/{self.variant_id} in cart {self.cart_id}"
