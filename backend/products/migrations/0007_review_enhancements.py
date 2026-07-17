import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("products", "0006_rename_products_pr_price_idx_products_pr_price_9b1a5f_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="verified_purchase",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="review",
            name="helpful_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="ReviewImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="reviews/")),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                (
                    "review",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="products.review",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="ReviewVote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "review",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="votes",
                        to="products.review",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="review_votes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="review",
            index=models.Index(
                fields=["product", "-helpful_count"], name="review_product_helpful_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="reviewvote",
            constraint=models.UniqueConstraint(
                fields=("review", "user"), name="uniq_vote_per_user_review"
            ),
        ),
    ]
