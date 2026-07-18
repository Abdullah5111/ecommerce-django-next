from django.db.models import Avg, Count
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Review, ReviewVote


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
    """Derive helpful_count from the vote rows themselves.

    Counting the source of truth (rather than incrementing a counter) is what
    keeps this correct when votes disappear without going through the vote
    endpoint — deleting a user cascades their ReviewVote rows, and a
    hand-maintained counter would stay inflated forever.
    """
    n = ReviewVote.objects.filter(review_id=review_id).count()
    Review.objects.filter(pk=review_id).update(helpful_count=n)


@receiver(post_save, sender=ReviewVote)
def review_vote_saved(sender, instance, **kwargs):
    _recompute_helpful(instance.review_id)


@receiver(post_delete, sender=ReviewVote)
def review_vote_deleted(sender, instance, **kwargs):
    # Deleting a Review cascades its votes; the .update() simply matches no
    # rows in that case, so the vanished review needs no special handling.
    _recompute_helpful(instance.review_id)
