from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("matching", "0014_step68_field_encryption"),
    ]

    operations = [
        migrations.AddField(
            model_name="caregiverprofile",
            name="photo",
            field=models.ImageField(blank=True, upload_to="profile_photos/caregivers/%Y/%m/"),
        ),
        migrations.AddField(
            model_name="patientprofile",
            name="photo",
            field=models.ImageField(blank=True, upload_to="profile_photos/patients/%Y/%m/"),
        ),
    ]
