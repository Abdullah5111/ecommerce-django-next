import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_user_address_to_address_rows(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Address = apps.get_model("accounts", "Address")
    for user in User.objects.all():
        legacy = (user.address or "").strip()
        if not legacy:
            continue
        line1 = legacy.splitlines()[0].strip()
        if not line1:
            continue
        full_name = f"{user.first_name} {user.last_name}".strip()
        recipient = full_name or user.username
        Address.objects.create(
            user=user,
            label="",
            recipient=recipient,
            phone=user.phone or "",
            line1=line1,
            line2="",
            city="",
            state="",
            postal_code="",
            country="US",
            is_default_shipping=True,
            is_default_billing=False,
        )


def reverse_migrate_addresses(apps, schema_editor):
    Address = apps.get_model("accounts", "Address")
    Address.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_user_email_verified"),
    ]

    operations = [
        migrations.CreateModel(
            name="Address",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(blank=True, max_length=50)),
                ("recipient", models.CharField(max_length=120)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("line1", models.CharField(max_length=200)),
                ("line2", models.CharField(blank=True, max_length=200)),
                ("city", models.CharField(max_length=100)),
                ("state", models.CharField(blank=True, max_length=100)),
                ("postal_code", models.CharField(max_length=20)),
                ("country", models.CharField(default="US", max_length=2)),
                ("is_default_shipping", models.BooleanField(default=False)),
                ("is_default_billing", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="addresses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-is_default_shipping", "-updated_at"],
            },
        ),
        migrations.RunPython(
            migrate_user_address_to_address_rows,
            reverse_migrate_addresses,
        ),
    ]
