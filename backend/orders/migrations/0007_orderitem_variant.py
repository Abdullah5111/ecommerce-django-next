import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0008_productvariant"),
        ("orders", "0006_order_tax_total"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="variant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="products.productvariant",
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="variant_sku",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="variant_label",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
