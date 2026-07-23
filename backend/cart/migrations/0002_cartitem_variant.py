import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0008_productvariant"),
        ("cart", "0001_initial"),
    ]

    operations = [
        # Drop the old (cart, product) uniqueness before adding the variant
        # dimension, then re-express it as two conditional constraints.
        migrations.AlterUniqueTogether(
            name="cartitem",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="cartitem",
            name="variant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="products.productvariant",
            ),
        ),
        migrations.AddConstraint(
            model_name="cartitem",
            constraint=models.UniqueConstraint(
                fields=("cart", "product"),
                condition=Q(variant__isnull=True),
                name="uniq_cart_product_no_variant",
            ),
        ),
        migrations.AddConstraint(
            model_name="cartitem",
            constraint=models.UniqueConstraint(
                fields=("cart", "product", "variant"),
                condition=Q(variant__isnull=False),
                name="uniq_cart_product_variant",
            ),
        ),
    ]
