from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="ship_recipient",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="order",
            name="ship_phone",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="order",
            name="ship_line1",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="order",
            name="ship_line2",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="order",
            name="ship_city",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="order",
            name="ship_state",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="order",
            name="ship_postal_code",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="order",
            name="ship_country",
            field=models.CharField(blank=True, max_length=2),
        ),
    ]
