# Step 68 — encrypt MatchRun query (transcript) + condition at rest.

from django.db import migrations, models


def forwards_encrypt_match_run(apps, schema_editor):
    from apps.common.encryption import encrypt_field

    MatchRun = apps.get_model("matching", "MatchRun")
    for row in MatchRun.objects.all().iterator():
        row.query_ciphertext = encrypt_field(getattr(row, "query", "") or "")
        row.condition_ciphertext = encrypt_field(getattr(row, "condition", "") or "")
        row.save(update_fields=["query_ciphertext", "condition_ciphertext"])


def backwards_decrypt_match_run(apps, schema_editor):
    from apps.common.encryption import decrypt_field

    MatchRun = apps.get_model("matching", "MatchRun")
    for row in MatchRun.objects.all().iterator():
        row.query = decrypt_field(row.query_ciphertext or "")
        row.condition = decrypt_field(row.condition_ciphertext or "")
        row.save(update_fields=["query", "condition"])


class Migration(migrations.Migration):

    dependencies = [
        ("matching", "0013_step51_shift_booking"),
    ]

    operations = [
        migrations.AddField(
            model_name="matchrun",
            name="condition_ciphertext",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="matchrun",
            name="query_ciphertext",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.RunPython(forwards_encrypt_match_run, backwards_decrypt_match_run),
        migrations.RemoveField(
            model_name="matchrun",
            name="condition",
        ),
        migrations.RemoveField(
            model_name="matchrun",
            name="query",
        ),
    ]
