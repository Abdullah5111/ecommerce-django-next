from django.db import migrations, models
from django.db.models import Sum

# Kept literal (not imported) so the migration stays stable if the app constant moves.
SOLD_STATUSES = ("paid", "shipped", "delivered", "partially_refunded", "refunded")


def backfill_sold_count(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    OrderItem = apps.get_model("orders", "OrderItem")
    rows = (
        OrderItem.objects.filter(order__status__in=SOLD_STATUSES)
        .values("product_id")
        .annotate(n=Sum("quantity"))
    )
    for row in rows:
        Product.objects.filter(pk=row["product_id"]).update(sold_count=row["n"] or 0)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0008_productvariant"),
        ("orders", "0007_orderitem_variant"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="sold_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["-sold_count"], name="products_pr_sold_idx"),
        ),
        migrations.RunPython(backfill_sold_count, noop),
    ]
