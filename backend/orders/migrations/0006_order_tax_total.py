from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_order_payment_intent_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="tax_total",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
