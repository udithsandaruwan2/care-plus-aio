"""Step 15g — DialogueSession memory + clear."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import ConsentLog, ConsentScope
from apps.matching.models import MatchResult, MatchRun
from apps.voice.dialogue import process_turn
from apps.voice.models import DialogueSession
from apps.voice.session import clear_active_sessions, get_or_create_active_session

User = get_user_model()


@override_settings(
    VOICE_INTENT_BACKEND="stub",
    ASR_BACKEND="client",
    DIALOGUE_CHAT_BACKEND="stub",
    TTS_BACKEND="browser",
)
class DialogueSessionMemoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="sess@example.com", password="pw-strong-123")

    def _seed_match_run(self) -> MatchRun:
        run = MatchRun.objects.create(
            user=self.user,
            query="diabetes Sinhala",
            condition="diabetes",
            language="Sinhala",
            care_level="intermediate",
            emergency=False,
            weights=[0.4, 0.1, 0.3, 0.2],
            latency_ms=12,
        )
        # MatchResult needs a caregiver FK — create a minimal one via matching profile.
        from django.contrib.gis.geos import Point

        from apps.accounts.models import Role
        from apps.matching.models import CaregiverProfile

        cg_user = User.objects.create_user(
            email="sess.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        cg = CaregiverProfile.objects.create(
            user=cg_user,
            display_name="Session Top CG",
            location=Point(79.86, 6.93, srid=4326),
            specialties=["diabetes"],
            languages=["Sinhala"],
            care_levels=["intermediate"],
            trust_score=0.9,
            is_active=True,
            is_approved=True,
        )
        MatchResult.objects.create(
            run=run,
            caregiver=cg,
            rank=1,
            score=0.92,
            cbf=0.9,
            cf=0.5,
            geo=0.8,
            trust=0.9,
            explanation="Matched because: strong medical/skill match.",
            distance_m=1200.0,
        )
        return run

    def test_session_persists_chips_and_turns(self):
        out = process_turn(
            user=self.user,
            client_text="hello",
            ui_language="English",
        )
        self.assertIsNotNone(out.get("session_id"))
        session = DialogueSession.objects.get(pk=out["session_id"])
        self.assertTrue(session.active)
        self.assertGreaterEqual(len(session.turns), 2)
        self.assertTrue(any(t.get("route") == "CHAT" for t in session.route_history))

    def test_about_match_uses_session_match_run(self):
        run = self._seed_match_run()
        session = get_or_create_active_session(self.user, lang="English")
        session.intent_chips = {
            "condition": "diabetes",
            "language": "Sinhala",
            "care_level": "intermediate",
        }
        session.last_match_run = run
        session.save()

        out = process_turn(
            user=self.user,
            client_text="why is number one ranked high?",
            ui_language="English",
            has_prior_match=False,  # server session should still count
        )
        self.assertEqual(out["situation"], "about_match")
        self.assertEqual(out["route"], "CHAT")
        self.assertFalse(out["clear_match"])
        self.assertIsNone(out.get("match"))
        self.assertIn("medical/skill", out["reply"].lower())
        session.refresh_from_db()
        self.assertEqual(session.last_match_run_id, run.pk)

    def test_clear_session_drops_memory(self):
        process_turn(user=self.user, client_text="hello", ui_language="English")
        self.assertEqual(DialogueSession.objects.filter(user=self.user, active=True).count(), 1)
        cleared = clear_active_sessions(self.user)
        self.assertEqual(cleared, 1)
        self.assertEqual(DialogueSession.objects.filter(user=self.user, active=True).count(), 0)


@override_settings(
    VOICE_INTENT_BACKEND="stub",
    ASR_BACKEND="client",
    DIALOGUE_CHAT_BACKEND="stub",
    TTS_BACKEND="browser",
)
class VoiceSessionApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="sessapi@example.com", password="pw-strong-123")
        ConsentLog.objects.create(user=self.user, scope=ConsentScope.AI_PROCESSING, granted=True)
        self.turn_url = reverse("v1:voice_turn")
        self.clear_url = reverse("v1:voice_session_clear")
        self.session_url = reverse("v1:voice_session")

    def test_turn_returns_session_id_and_clear_works(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(self.turn_url, {"text": "hello", "ui_language": "English"}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("session_id", resp.data)
        sid = resp.data["session_id"]

        resp = self.client.get(self.session_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["active"])
        self.assertEqual(resp.data["session"]["id"], sid)

        resp = self.client.post(self.clear_url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data["cleared"], 1)

        resp = self.client.get(self.session_url)
        self.assertFalse(resp.data["active"])
