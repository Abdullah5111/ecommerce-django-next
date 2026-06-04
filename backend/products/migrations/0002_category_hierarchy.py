import django.db.models.deletion
from django.db import migrations, models


def populate_full_slug(apps, schema_editor):
    Category = apps.get_model("products", "Category")
    for cat in Category.objects.all():
        cat.full_slug = cat.slug
        cat.level = 0
        cat.save(update_fields=["full_slug", "level"])


def reverse_full_slug(apps, schema_editor):
    Category = apps.get_model("products", "Category")
    Category.objects.all().update(full_slug="", level=0)


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="children",
                to="products.category",
            ),
        ),
        migrations.AddField(
            model_name="category",
            name="full_slug",
            field=models.CharField(blank=True, max_length=512, default="", unique=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="category",
            name="level",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.RunPython(populate_full_slug, reverse_full_slug),
        migrations.AlterField(
            model_name="category",
            name="full_slug",
            field=models.CharField(blank=True, max_length=512, unique=True),
        ),
    ]
