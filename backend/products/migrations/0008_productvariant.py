import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0007_review_enhancements"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductVariant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("options", models.JSONField(default=dict)),
                ("sku", models.CharField(max_length=64, unique=True)),
                ("stock", models.PositiveIntegerField(default=0)),
                ("price", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="variants",
                        to="products.product",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.AddIndex(
            model_name="productvariant",
            index=models.Index(fields=["product", "is_active"], name="products_pr_product_var_idx"),
        ),
        migrations.AddConstraint(
            model_name="productvariant",
            constraint=models.UniqueConstraint(
                fields=("product", "options"), name="uniq_variant_options_per_product"
            ),
        ),
    ]
