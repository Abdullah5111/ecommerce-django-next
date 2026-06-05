import django.db.models.deletion
from django.db import migrations, models


def copy_image_url_to_product_image(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ProductImage = apps.get_model("products", "ProductImage")
    for product in Product.objects.all():
        if product.image_url:
            ProductImage.objects.create(
                product=product,
                url=product.image_url,
                sort_order=0,
            )


def remove_seeded_product_images(apps, schema_editor):
    ProductImage = apps.get_model("products", "ProductImage")
    ProductImage.objects.filter(sort_order=0).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0002_category_hierarchy"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="compare_at_price",
            field=models.DecimalField(
                max_digits=10, decimal_places=2, null=True, blank=True
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="rating_avg",
            field=models.DecimalField(max_digits=3, decimal_places=2, default=0),
        ),
        migrations.AddField(
            model_name="product",
            name="rating_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="ProductImage",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("url", models.URLField(max_length=500)),
                ("alt", models.CharField(blank=True, max_length=200)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="products.product",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.RunPython(
            copy_image_url_to_product_image, remove_seeded_product_images
        ),
    ]
