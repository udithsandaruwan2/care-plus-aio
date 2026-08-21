# Generated for Step 104

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("matching", "0020_step102_matchrun_variant"),
    ]

    operations = [
        migrations.AddField(
            model_name="matchrun",
            name="deleted_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
