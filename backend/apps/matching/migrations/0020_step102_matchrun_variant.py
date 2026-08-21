# Generated for Step 102

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("matching", "0019_step100_matchresult_was_exploratory"),
    ]

    operations = [
        migrations.AddField(
            model_name="matchrun",
            name="variant",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="matchrun",
            name="weights_source",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
