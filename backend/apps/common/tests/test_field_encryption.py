"""Step 68 — field encryption for health payloads + voice intent."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import Role
from apps.common.encryption import encrypt_field, encrypt_json
from apps.health_monitoring.models import HealthEvent, HealthEventType, HealthMetric, HealthMetricKind
from apps.matching.models import create_match_run
from apps.voice.models import DialogueSession, create_voice_intent

User = get_user_model()


@override_settings(FIELD_ENCRYPTION_KEY="")
class Step68FieldEncryptionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="enc68@example.com",
            password="pw-strong-123",
            role=Role.PATIENT,
        )

    def test_voice_intent_encrypted_at_rest(self):
        intent = create_voice_intent(
            user=self.user,
            raw_text="මට දියවැඩියාව තියෙනවා",
            condition="diabetes",
            language="Sinhala",
            languages=["Sinhala"],
            care_level="intermediate",
            urgency="routine",
            source="stub",
        )
        stored = type(intent).objects.get(pk=intent.pk)
        self.assertNotEqual(stored.raw_text_ciphertext, "මට දියවැඩියාව තියෙනවා")
        self.assertNotEqual(stored.condition_ciphertext, "diabetes")
        self.assertEqual(stored.raw_text, "මට දියවැඩියාව තියෙනවා")
        self.assertEqual(stored.condition, "diabetes")

    def test_dialogue_turns_encrypted_at_rest(self):
        session = DialogueSession.objects.create(user=self.user, active=True)
        session.turns = [{"role": "user", "text": "I have dengue", "route": "MATCH"}]
        session.intent_chips = {"condition": "dengue", "language": "English"}
        session.save()
        stored = DialogueSession.objects.get(pk=session.pk)
        self.assertNotIn("dengue", stored.turns_ciphertext)
        self.assertNotIn("I have dengue", stored.turns_ciphertext)
        self.assertEqual(stored.turns[0]["text"], "I have dengue")
        self.assertEqual(stored.intent_chips["condition"], "dengue")

    def test_health_metadata_and_payload_encrypted(self):
        metric = HealthMetric(
            patient=self.user,
            kind=HealthMetricKind.BLOOD_GLUCOSE,
            value=220.0,
            unit="mg/dL",
            recorded_at=timezone.now(),
        )
        metric.metadata = {"device": "glucometer-A", "note": "fasting"}
        metric.save()
        stored_m = HealthMetric.objects.get(pk=metric.pk)
        self.assertNotIn("fasting", stored_m.metadata_ciphertext)
        self.assertEqual(stored_m.metadata["note"], "fasting")

        event = HealthEvent(
            patient=self.user,
            event_type=HealthEventType.HEALTH_CRITICAL,
            kind=HealthMetricKind.BLOOD_GLUCOSE,
            rule_key="glucose_high",
            window_start=timezone.now(),
            window_end=timezone.now(),
            sample_count=3,
        )
        event.payload = {"samples": [210, 220, 230], "unit": "mg/dL"}
        event.save()
        stored_e = HealthEvent.objects.get(pk=event.pk)
        self.assertNotIn("220", stored_e.payload_ciphertext)
        self.assertEqual(stored_e.payload["samples"], [210, 220, 230])

    def test_match_run_query_encrypted(self):
        run = create_match_run(
            user=self.user,
            query="need Sinhala caregiver for dengue",
            condition="dengue",
            language="Sinhala",
            care_level="intermediate",
            weights=[0.4, 0.1, 0.3, 0.2],
            latency_ms=10,
        )
        stored = type(run).objects.get(pk=run.pk)
        self.assertNotEqual(stored.query_ciphertext, "need Sinhala caregiver for dengue")
        self.assertEqual(stored.query, "need Sinhala caregiver for dengue")
        self.assertEqual(stored.condition, "dengue")

    def test_shared_encrypt_helpers(self):
        self.assertNotEqual(encrypt_field("secret"), "secret")
        self.assertNotEqual(encrypt_json({"a": 1}), '{"a":1}')
