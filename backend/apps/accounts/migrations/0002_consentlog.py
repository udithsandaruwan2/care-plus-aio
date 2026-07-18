# Generated for Care Plus Step 7 — consent engine (PDPA/GDPR gate).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConsentLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "scope",
                    models.CharField(
                        choices=[
                            ("ai_processing", "AI processing of voice/intent"),
                            ("health_monitoring", "Health time-series monitoring"),
                            ("data_sharing", "Sharing profile with matched caregivers"),
                        ],
                        max_length=32,
                    ),
                ),
                ("granted", models.BooleanField()),
                ("ts", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="consent_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-ts",),
            },
        ),
        migrations.AddIndex(
            model_name="consentlog",
            index=models.Index(fields=["user", "scope", "-ts"], name="consent_user_scope_ts_idx"),
        ),
    ]
