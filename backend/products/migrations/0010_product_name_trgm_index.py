from django.db import migrations

# Postgres-only: a trigram GIN index makes the autocomplete's `name__icontains`
# (a leading-wildcard `%q%` scan) index-backed instead of a sequential scan.
# Guarded by vendor so SQLite dev/test still migrates (there it stays a scan).


def add_trgm_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    schema_editor.execute(
        "CREATE INDEX IF NOT EXISTS products_pr_name_trgm "
        "ON products_product USING gin (name gin_trgm_ops)"
    )


def drop_trgm_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP INDEX IF EXISTS products_pr_name_trgm")


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0009_product_sold_count"),
    ]

    operations = [
        migrations.RunPython(add_trgm_index, drop_trgm_index),
    ]
