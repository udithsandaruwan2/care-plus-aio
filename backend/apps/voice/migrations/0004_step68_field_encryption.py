# Step 68 — encrypt VoiceIntent transcript/condition + DialogueSession memory.

from django.db import migrations, models


def forwards_encrypt_voice(apps, schema_editor):
    from apps.common.encryption import encrypt_field, encrypt_json

    VoiceIntent = apps.get_model("voice", "VoiceIntent")
    DialogueSession = apps.get_model("voice", "DialogueSession")

    for row in VoiceIntent.objects.all().iterator():
        row.raw_text_ciphertext = encrypt_field(getattr(row, "raw_text", "") or "")
        row.condition_ciphertext = encrypt_field(getattr(row, "condition", "") or "")
        row.save(update_fields=["raw_text_ciphertext", "condition_ciphertext"])

    for row in DialogueSession.objects.all().iterator():
        row.turns_ciphertext = encrypt_json(getattr(row, "turns", None) or [])
        row.intent_chips_ciphertext = encrypt_json(getattr(row, "intent_chips", None) or {})
        row.save(update_fields=["turns_ciphertext", "intent_chips_ciphertext"])


def backwards_decrypt_voice(apps, schema_editor):
    from apps.common.encryption import decrypt_field, decrypt_json

    VoiceIntent = apps.get_model("voice", "VoiceIntent")
    DialogueSession = apps.get_model("voice", "DialogueSession")

    for row in VoiceIntent.objects.all().iterator():
        row.raw_text = decrypt_field(row.raw_text_ciphertext or "")
        row.condition = decrypt_field(row.condition_ciphertext or "")
        row.save(update_fields=["raw_text", "condition"])

    for row in DialogueSession.objects.all().iterator():
        row.turns = decrypt_json(row.turns_ciphertext or "", default=[])
        row.intent_chips = decrypt_json(row.intent_chips_ciphertext or "", default={})
        row.save(update_fields=["turns", "intent_chips"])


class Migration(migrations.Migration):

    dependencies = [
        ("voice", "0003_dialogue_session"),
    ]

    operations = [
        migrations.AddField(
            model_name="dialoguesession",
            name="intent_chips_ciphertext",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="dialoguesession",
            name="turns_ciphertext",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="voiceintent",
            name="condition_ciphertext",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="voiceintent",
            name="raw_text_ciphertext",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.RunPython(forwards_encrypt_voice, backwards_decrypt_voice),
        migrations.RemoveField(
            model_name="dialoguesession",
            name="intent_chips",
        ),
        migrations.RemoveField(
            model_name="dialoguesession",
            name="turns",
        ),
        migrations.RemoveField(
            model_name="voiceintent",
            name="condition",
        ),
        migrations.RemoveField(
            model_name="voiceintent",
            name="raw_text",
        ),
    ]
