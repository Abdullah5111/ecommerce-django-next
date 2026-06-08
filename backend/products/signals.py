from django.db.models import Avg, Count
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Review


def _recompute(product):
    agg = product.reviews.aggregate(avg=Avg("rating"), n=Count("id"))
    product.rating_avg = round(agg["avg"] or 0, 2)
    product.rating_count = agg["n"] or 0
    product.save(update_fields=["rating_avg", "rating_count"])


@receiver(post_save, sender=Review)
def review_saved(sender, instance, **kwargs):
    _recompute(instance.product)


@receiver(post_delete, sender=Review)
def review_deleted(sender, instance, **kwargs):
    _recompute(instance.product)
