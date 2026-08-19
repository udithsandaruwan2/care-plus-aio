# Step 79 — MatchRun provenance for replay

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("matching", "0016_step76_interaction_reject"),
        ("voice", "0005_step77_turn_timing"),
    ]

    operations = [
        migrations.AddField(
            model_name="matchrun",
            name="cf_version",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="matchrun",
            name="embedding_backend",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="matchrun",
            name="index_version",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="matchrun",
            name="weights_source",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="matchrun",
            name="filters",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="matchrun",
            name="request_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="matchrun",
            name="voice_intent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="match_runs",
                to="voice.voiceintent",
            ),
        ),
    ]
