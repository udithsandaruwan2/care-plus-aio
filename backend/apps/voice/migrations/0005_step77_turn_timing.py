# Step 77 — VoiceTurnTiming (per-stage /voice/turn/ latency).

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("voice", "0004_step68_field_encryption"),
    ]

    operations = [
        migrations.CreateModel(
            name="VoiceTurnTiming",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("request_id", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("route", models.CharField(blank=True, default="", max_length=16)),
                ("situation", models.CharField(blank=True, default="", max_length=32)),
                ("asr_ms", models.PositiveIntegerField(default=0)),
                ("intent_ms", models.PositiveIntegerField(default=0)),
                ("route_ms", models.PositiveIntegerField(default=0)),
                ("match_ms", models.PositiveIntegerField(default=0)),
                ("chat_ms", models.PositiveIntegerField(default=0)),
                ("tts_ms", models.PositiveIntegerField(default=0)),
                ("total_ms", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="voice_turn_timings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
    ]
