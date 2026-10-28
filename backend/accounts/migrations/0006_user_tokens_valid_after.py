from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_alter_user_groups_alter_user_is_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="tokens_valid_after",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
