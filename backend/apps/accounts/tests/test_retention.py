"""Step 106 — retention TTLs, session wipe, health downsample."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.retention import (
    DOWNSAMPLED_SOURCE,
    apply_retention_policy,
    anonymize_stale_voice_intents,
    downsample_stale_health_metrics,
    scrub_stale_dialogue_sessions,
)
from apps.health_monitoring.models import HealthMetric, HealthMetricKind
from apps.voice.models import DialogueSession, create_voice_intent
from apps.voice.session import clear_active_sessions, get_or_create_active_session

User = get_user_model()


class SessionClearWipesTurnsTests(TestCase):
    def test_clear_leaves_no_recoverable_turn_text(self):
        user = User.objects.create_user(
            email="ret.sess@example.com", password="pw-strong-123", role=Role.PATIENT
        )
        session = get_or_create_active_session(user, lang="English")
        session.turns = [
            {"role": "user", "text": "secret diabetes transcript", "route": "CHAT", "situation": ""}
        ]
        session.route_history = [{"route": "CHAT", "situation": ""}]
        session.intent_chips = {"condition": "diabetes"}
        session.save()

        cleared = clear_active_sessions(user)
        self.assertEqual(cleared, 1)
        session.refresh_from_db()
        self.assertFalse(session.active)
        self.assertEqual(session.turns, [])
        self.assertEqual(session.route_history, [])
        self.assertEqual(session.intent_chips, {})
        self.assertNotIn("diabetes", session.turns_ciphertext)
        self.assertNotIn("secret", session.turns_ciphertext)


@override_settings(
    RETENTION_VOICE_INTENT_DAYS=30,
    RETENTION_DIALOGUE_SESSION_DAYS=14,
    RETENTION_HEALTH_METRIC_RAW_DAYS=30,
)
class RetentionPolicyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ret.pt@example.com", password="pw-strong-123", role=Role.PATIENT
        )

    def test_anonymize_stale_voice_intents(self):
        old = create_voice_intent(
            user=self.user,
            raw_text="old transcript PHI",
            condition="dengue",
            language="English",
            care_level="basic",
            source="stub",
        )
        fresh = create_voice_intent(
            user=self.user,
            raw_text="fresh transcript",
            condition="asthma",
            language="English",
            care_level="basic",
            source="stub",
        )
        VoiceIntent = old.__class__
        VoiceIntent.objects.filter(pk=old.pk).update(ts=timezone.now() - timedelta(days=45))

        n = anonymize_stale_voice_intents(days=30)
        self.assertEqual(n, 1)
        old.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual(old.raw_text, "")
        self.assertEqual(old.condition, "")
        self.assertEqual(old.language, "English")
        self.assertEqual(fresh.raw_text, "fresh transcript")

        # Idempotent
        self.assertEqual(anonymize_stale_voice_intents(days=30), 0)

    def test_scrub_stale_inactive_sessions(self):
        session = DialogueSession.objects.create(user=self.user, active=False, lang="English")
        session.turns = [{"role": "user", "text": "stale turn text", "route": "CHAT"}]
        session.route_history = [{"route": "MATCH"}]
        session.save()
        DialogueSession.objects.filter(pk=session.pk).update(
            updated_at=timezone.now() - timedelta(days=40)
        )

        active = get_or_create_active_session(self.user)
        active.turns = [{"role": "user", "text": "keep me", "route": "CHAT"}]
        active.save()

        n = scrub_stale_dialogue_sessions(days=14)
        self.assertEqual(n, 1)
        session.refresh_from_db()
        active.refresh_from_db()
        self.assertEqual(session.turns, [])
        self.assertEqual(session.route_history, [])
        self.assertEqual(active.turns[0]["text"], "keep me")
        self.assertEqual(scrub_stale_dialogue_sessions(days=14), 0)

    def test_downsample_health_metrics(self):
        old_day = timezone.now() - timedelta(days=45)
        for i, val in enumerate([100.0, 110.0, 120.0]):
            HealthMetric.objects.create(
                patient=self.user,
                kind=HealthMetricKind.HEART_RATE,
                value=val,
                unit="bpm",
                source="manual",
                recorded_at=old_day + timedelta(minutes=i),
            )
        HealthMetric.objects.create(
            patient=self.user,
            kind=HealthMetricKind.HEART_RATE,
            value=72.0,
            unit="bpm",
            source="manual",
            recorded_at=timezone.now() - timedelta(hours=1),
        )

        stats = downsample_stale_health_metrics(days=30)
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["deleted"], 3)
        downs = HealthMetric.objects.filter(patient=self.user, source=DOWNSAMPLED_SOURCE)
        self.assertEqual(downs.count(), 1)
        self.assertAlmostEqual(downs.first().value, 110.0)
        self.assertEqual(
            HealthMetric.objects.filter(patient=self.user, source="manual").count(), 1
        )

        # Second run is a no-op
        stats2 = downsample_stale_health_metrics(days=30)
        self.assertEqual(stats2["created"], 0)
        self.assertEqual(stats2["deleted"], 0)
        self.assertEqual(downs.count(), 1)

    def test_apply_retention_policy_bundle(self):
        out = apply_retention_policy()
        self.assertIn("voice_intents_anonymized", out)
        self.assertIn("dialogue_sessions_scrubbed", out)
        self.assertIn("health_metrics", out)
        self.assertEqual(out["ttls"]["voice_intent_days"], 30)
