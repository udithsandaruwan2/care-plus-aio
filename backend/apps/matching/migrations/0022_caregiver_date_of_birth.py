from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("matching", "0021_step104_matchrun_deleted_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="caregiverprofile",
            name="date_of_birth",
            field=models.DateField(blank=True, null=True),
        ),
    ]
