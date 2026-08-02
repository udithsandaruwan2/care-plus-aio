# Step 68 — encrypt HealthMetric.metadata + HealthEvent.payload at rest.

from django.db import migrations, models


def forwards_encrypt_health(apps, schema_editor):
    from apps.common.encryption import encrypt_json

    HealthMetric = apps.get_model("health_monitoring", "HealthMetric")
    HealthEvent = apps.get_model("health_monitoring", "HealthEvent")

    for row in HealthMetric.objects.all().iterator():
        row.metadata_ciphertext = encrypt_json(getattr(row, "metadata", None) or {})
        row.save(update_fields=["metadata_ciphertext"])

    for row in HealthEvent.objects.all().iterator():
        row.payload_ciphertext = encrypt_json(getattr(row, "payload", None) or {})
        row.save(update_fields=["payload_ciphertext"])


def backwards_decrypt_health(apps, schema_editor):
    from apps.common.encryption import decrypt_json

    HealthMetric = apps.get_model("health_monitoring", "HealthMetric")
    HealthEvent = apps.get_model("health_monitoring", "HealthEvent")

    for row in HealthMetric.objects.all().iterator():
        row.metadata = decrypt_json(row.metadata_ciphertext or "", default={})
        row.save(update_fields=["metadata"])

    for row in HealthEvent.objects.all().iterator():
        row.payload = decrypt_json(row.payload_ciphertext or "", default={})
        row.save(update_fields=["payload"])


class Migration(migrations.Migration):

    dependencies = [
        ("health_monitoring", "0003_step47_event_dispatch_tracking"),
    ]

    operations = [
        migrations.AddField(
            model_name="healthevent",
            name="payload_ciphertext",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="healthmetric",
            name="metadata_ciphertext",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.RunPython(forwards_encrypt_health, backwards_decrypt_health),
        migrations.RemoveField(
            model_name="healthevent",
            name="payload",
        ),
        migrations.RemoveField(
            model_name="healthmetric",
            name="metadata",
        ),
    ]
