from django.db.models import Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from products.models import Product

from .models import Order, OrderItem

# Order statuses whose line items count toward Product.sold_count. Mirrors
# products.views.SOLD_STATUSES (cancellation restocks, so it's excluded).
SOLD_STATUSES = ("paid", "shipped", "delivered", "partially_refunded", "refunded")


def _recompute_sold(product_id):
    """Recompute one product's denormalized sold_count from its order lines.
    Runs only on order writes (rare), keeping it off every catalog read.
    """
    if not product_id:
        return
    total = (
        OrderItem.objects.filter(
            product_id=product_id, order__status__in=SOLD_STATUSES
        ).aggregate(n=Sum("quantity"))["n"]
        or 0
    )
    Product.objects.filter(pk=product_id).update(sold_count=total)


@receiver(post_save, sender=OrderItem)
def orderitem_saved(sender, instance, **kwargs):
    _recompute_sold(instance.product_id)


@receiver(post_delete, sender=OrderItem)
def orderitem_deleted(sender, instance, **kwargs):
    _recompute_sold(instance.product_id)


@receiver(post_save, sender=Order)
def order_saved(sender, instance, **kwargs):
    # A status change moves every line into or out of the sold set; recompute all.
    for pid in instance.items.values_list("product_id", flat=True).distinct():
        _recompute_sold(pid)
