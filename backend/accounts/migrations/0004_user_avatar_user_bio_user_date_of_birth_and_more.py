from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_address"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="avatar",
            field=models.ImageField(blank=True, null=True, upload_to="avatars/"),
        ),
        migrations.AddField(
            model_name="user",
            name="bio",
            field=models.CharField(blank=True, max_length=280),
        ),
        migrations.AddField(
            model_name="user",
            name="date_of_birth",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="display_name",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AddField(
            model_name="user",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[
                    ("female", "Female"),
                    ("male", "Male"),
                    ("nonbinary", "Non-binary"),
                    ("prefer_not_to_say", "Prefer not to say"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="phone_verified",
            field=models.BooleanField(default=False),
        ),
    ]
