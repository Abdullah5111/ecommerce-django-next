from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0003_product_images_and_pricing"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="is_featured",
            field=models.BooleanField(default=False),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["price"], name="products_pr_price_idx"),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["is_active"], name="products_pr_active_idx"),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["is_featured"], name="products_pr_featured_idx"),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["stock"], name="products_pr_stock_idx"),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(
                fields=["category", "is_active", "-created_at"],
                name="products_pr_cat_act_crt_idx",
            ),
        ),
    ]
