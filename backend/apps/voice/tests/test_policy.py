"""Step 15j — dialogue AI policy: stub without key, rate limit, VEHMF-only match."""

import tempfile

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import ConsentLog, ConsentScope, Role
from apps.matching.faiss_index import build_index, reset_cache
from apps.matching.models import CaregiverProfile
from apps.voice.dialogue import process_turn
from apps.voice.policy import gemini_chat_allowed, policy_snapshot, resolve_chat_backend
from apps.voice.replies import serah_reply

User = get_user_model()


class PolicyResolveTests(SimpleTestCase):
    @override_settings(DIALOGUE_CHAT_BACKEND="stub", GEMINI_API_KEY="fake-key")
    def test_explicit_stub_wins(self):
        self.assertEqual(resolve_chat_backend(), "stub")

    @override_settings(DIALOGUE_CHAT_BACKEND="gemini", GEMINI_API_KEY="")
    def test_gemini_without_key_falls_to_stub(self):
        self.assertEqual(resolve_chat_backend(), "stub")

    @override_settings(DIALOGUE_CHAT_BACKEND="", GEMINI_API_KEY="")
    def test_empty_backend_no_key_is_stub(self):
        self.assertEqual(resolve_chat_backend(), "stub")


@override_settings(
    DIALOGUE_CHAT_BACKEND="gemini",
    GEMINI_API_KEY="fake-key",
    DIALOGUE_GEMINI_RATE_LIMIT=2,
    DIALOGUE_GEMINI_RATE_WINDOW_SEC=3600,
)
class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email="rate@example.com", password="pw-strong-123")

    def test_rate_limit_trips(self):
        ok, reason = gemini_chat_allowed(self.user.pk)
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")
        ok, reason = gemini_chat_allowed(self.user.pk)
        self.assertTrue(ok)
        ok, reason = gemini_chat_allowed(self.user.pk)
        self.assertFalse(ok)
        self.assertEqual(reason, "rate_limited")

    def test_serah_rate_limited_uses_stub_text(self):
        gemini_chat_allowed(self.user.pk)
        gemini_chat_allowed(self.user.pk)
        line = serah_reply(
            text="hello",
            lang="en-US",
            situation="greeting",
            user_id=self.user.pk,
        )
        self.assertEqual(line.source, "rate_limited")
        self.assertTrue(line.text)


@override_settings(
    VOICE_INTENT_BACKEND="stub",
    ASR_BACKEND="client",
    DIALOGUE_CHAT_BACKEND="stub",
    TTS_BACKEND="browser",
    GEMINI_API_KEY="",
    EMBEDDING_BACKEND="hash",
)
class StubChatAndLocalMatchTests(TestCase):
    def setUp(self):
        reset_cache()
        self.user = User.objects.create_user(email="pol@example.com", password="pw-strong-123")
        cg = User.objects.create_user(
            email="pol.cg@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        CaregiverProfile.objects.create(
            user=cg,
            display_name="Policy Diabetes CG",
            location=Point(79.86, 6.93, srid=4326),
            specialties=["diabetes"],
            languages=["Sinhala", "English"],
            care_levels=["intermediate"],
            trust_score=0.9,
            is_available=True,
        )

    def test_chat_stub_without_gemini_key(self):
        out = process_turn(user=self.user, client_text="hello", ui_language="English")
        self.assertEqual(out["route"], "CHAT")
        self.assertEqual(out["chat_source"], "stub")
        self.assertEqual(out["chat_backend"], "stub")
        self.assertTrue(out["reply"])

    def test_match_still_uses_vehmf_without_gemini(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(FAISS_ARTIFACT_DIR=tmp):
                reset_cache()
                build_index(persist=True)
                out = process_turn(
                    user=self.user,
                    client_text="find me a caregiver for diabetes Sinhala intermediate",
                    ui_language="English",
                    prior_intent={
                        "condition": "diabetes",
                        "language": "Sinhala",
                        "care_level": "intermediate",
                    },
                )
                self.assertEqual(out["route"], "MATCH")
                self.assertEqual(out["match_engine"], "vehmf")
                self.assertEqual(out["chat_source"], "vehmf")
                self.assertIsNotNone(out.get("match"))
                self.assertGreaterEqual(len(out["match"]["results"]), 1)


@override_settings(DIALOGUE_CHAT_BACKEND="stub", GEMINI_API_KEY="")
class PolicyApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="polapi@example.com", password="pw-strong-123")
        ConsentLog.objects.create(user=self.user, scope=ConsentScope.AI_PROCESSING, granted=True)

    def test_policy_endpoint(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(reverse("v1:voice_dialogue_policy"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["match_engine"], "vehmf")
        self.assertFalse(resp.data["gemini_ranks_caregivers"])
        self.assertEqual(resp.data["chat_backend"], "stub")
        snap = policy_snapshot()
        self.assertEqual(snap["match_engine"], "vehmf")
