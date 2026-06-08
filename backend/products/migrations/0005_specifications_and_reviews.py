from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0004_product_indexes_and_featured"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="specifications",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name="Review",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("author_name", models.CharField(blank=True, max_length=120)),
                ("rating", models.PositiveSmallIntegerField()),
                ("title", models.CharField(blank=True, max_length=200)),
                ("body", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reviews",
                        to="products.product",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="review",
            index=models.Index(
                fields=["product", "-created_at"],
                name="products_re_product_created_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="review",
            constraint=models.UniqueConstraint(
                condition=models.Q(("user__isnull", False)),
                fields=("product", "user"),
                name="uniq_review_per_user_product",
            ),
        ),
        migrations.AddConstraint(
            model_name="review",
            constraint=models.CheckConstraint(
                check=models.Q(("rating__gte", 1), ("rating__lte", 5)),
                name="review_rating_1_to_5",
            ),
        ),
    ]
