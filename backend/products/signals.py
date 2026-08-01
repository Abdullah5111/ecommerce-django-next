from django.db.models import Avg, Count
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Review, ReviewImage, ReviewVote


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


def _recompute_helpful(review_id):
    """Derive helpful_count from the vote rows themselves — counting the source
    of truth stays correct when votes vanish outside the endpoint (e.g. user delete).
    """
    n = ReviewVote.objects.filter(review_id=review_id).count()
    Review.objects.filter(pk=review_id).update(helpful_count=n)


@receiver(post_save, sender=ReviewVote)
def review_vote_saved(sender, instance, **kwargs):
    _recompute_helpful(instance.review_id)


@receiver(post_delete, sender=ReviewVote)
def review_vote_deleted(sender, instance, **kwargs):
    # Review delete cascades its votes; the .update() then matches no rows.
    _recompute_helpful(instance.review_id)


@receiver(post_delete, sender=ReviewImage)
def review_image_deleted(sender, instance, **kwargs):
    """Drop the stored file when its row goes — otherwise cascade-deleted
    ReviewImage files outlive their rows forever (unbounded on GCS).
    """
    if not instance.image:
        return
    # save=False: the row is already gone. Safe if the file is already missing.
    instance.image.delete(save=False)
