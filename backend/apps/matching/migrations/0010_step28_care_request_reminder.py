# Generated manually for Step 28

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("matching", "0009_step25_care_relationship"),
    ]

    operations = [
        migrations.AddField(
            model_name="carerequest",
            name="reminder_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
