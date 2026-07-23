from django.conf import settings
from django.db import models

from products.models import Product


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        PARTIALLY_REFUNDED = "partially_refunded", "Partially refunded"
        REFUNDED = "refunded", "Refunded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    shipping_address = models.TextField()
    ship_recipient = models.CharField(max_length=120, blank=True)
    ship_phone = models.CharField(max_length=30, blank=True)
    ship_line1 = models.CharField(max_length=200, blank=True)
    ship_line2 = models.CharField(max_length=200, blank=True)
    ship_city = models.CharField(max_length=100, blank=True)
    ship_state = models.CharField(max_length=100, blank=True)
    ship_postal_code = models.CharField(max_length=20, blank=True)
    ship_country = models.CharField(max_length=2, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon = models.ForeignKey(
        "coupons.Coupon", null=True, blank=True, on_delete=models.SET_NULL, related_name="orders"
    )
    coupon_code = models.CharField(max_length=40, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    tracking_carrier = models.CharField(max_length=60, blank=True)
    payment_intent_id = models.CharField(max_length=255, blank=True)
    refunded_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} ({self.user})"


class OrderEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    message = models.CharField(max_length=255)
    to_status = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Order #{self.order_id}: {self.message}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    # Optional — null for products bought without variants. PROTECT so a sold
    # variant can't be deleted out from under order history; the snapshot below
    # is the belt-and-braces copy for display regardless.
    variant = models.ForeignKey(
        "products.ProductVariant", on_delete=models.PROTECT, null=True, blank=True
    )
    variant_sku = models.CharField(max_length=64, blank=True)
    variant_label = models.CharField(max_length=200, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        return self.unit_price * self.quantity
