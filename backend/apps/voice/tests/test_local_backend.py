"""Step 97 — local intent backend + optional local chat endpoint."""

from __future__ import annotations

import json
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import ConsentLog, ConsentScope, Role
from apps.matching.faiss_index import build_index, reset_cache
from apps.matching.models import CaregiverProfile
from apps.voice.backends import extract_intent, extract_local
from apps.voice.dialogue import process_turn
from apps.voice.local_llm import post_chat_completion
from apps.voice.policy import policy_snapshot, resolve_chat_backend
from apps.voice.replies import serah_reply
from apps.voice.slots import train_slot_classifier

User = get_user_model()

SINHALA_DIABETES = "මට දියවැඩියාව තියෙනවා, සිංහල කතා කරන caregiver ඕනේ."


class LocalIntentBackendTests(TestCase):
    def test_local_without_classifier_falls_to_stub(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(
                SLOT_ARTIFACT_DIR=tmp,
                VOICE_INTENT_BACKEND="local",
                GEMINI_API_KEY="",
            ):
                from apps.voice import slots as slots_mod

                slots_mod._ACTIVE = None
                out = extract_local(SINHALA_DIABETES)
                self.assertEqual(out["source"], "stub")
                self.assertEqual(out["intent_backend"], "local")
                self.assertEqual(out["fallback_reason"], "no_active_slot_classifier")
                self.assertEqual(out["condition"], "diabetes")
                self.assertEqual(out["language"], "Sinhala")

    def test_local_uses_slot_classifier_when_trained(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(
                SLOT_ARTIFACT_DIR=tmp,
                SLOT_GATED_PROMOTION=False,
                VOICE_INTENT_BACKEND="local",
                GEMINI_API_KEY="",
            ):
                from apps.voice import slots as slots_mod

                slots_mod._ACTIVE = None
                train_slot_classifier(force=True, include_voice_intents=False)
                slots_mod._ACTIVE = None
                out = extract_intent("insulin shots every morning and evening")
                self.assertEqual(out["source"], "slot_classifier")
                self.assertEqual(out["intent_backend"], "local")
                self.assertEqual(out["fallback_reason"], "")
                self.assertEqual(out["condition"], "diabetes")


@override_settings(GEMINI_API_KEY="")
class ChatBackendResolveTests(SimpleTestCase):
    @override_settings(DIALOGUE_CHAT_BACKEND="local", LOCAL_LLM_URL="")
    def test_local_without_url_is_stub(self):
        self.assertEqual(resolve_chat_backend(), "stub")

    @override_settings(DIALOGUE_CHAT_BACKEND="local", LOCAL_LLM_URL="http://127.0.0.1:11434")
    def test_local_with_url(self):
        self.assertEqual(resolve_chat_backend(), "local")

    @override_settings(DIALOGUE_CHAT_BACKEND="", LOCAL_LLM_URL="http://127.0.0.1:11434", GEMINI_API_KEY="")
    def test_blank_prefers_local_when_no_gemini(self):
        self.assertEqual(resolve_chat_backend(), "local")


class LocalLlmHttpTests(SimpleTestCase):
    @override_settings(LOCAL_LLM_URL="http://127.0.0.1:9", LOCAL_LLM_TIMEOUT_SEC=0.2)
    def test_post_chat_completion_returns_none_on_failure(self):
        self.assertIsNone(post_chat_completion(system="sys", user="hi"))

    @override_settings(LOCAL_LLM_URL="http://example.test/v1", LOCAL_LLM_MODEL="demo")
    def test_serah_local_chat_uses_endpoint(self):
        payload = json.dumps(
            {"choices": [{"message": {"content": "Hello from local Serah."}}]}
        ).encode()

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return payload

        with override_settings(DIALOGUE_CHAT_BACKEND="local", LOCAL_LLM_URL="http://example.test/v1"):
            with patch("urllib.request.urlopen", return_value=_Resp()):
                line = serah_reply(text="hi", lang="en-US", situation="greeting")
        self.assertEqual(line.source, "local_llm")
        self.assertIn("local Serah", line.text)


@override_settings(
    VOICE_INTENT_BACKEND="local",
    ASR_BACKEND="client",
    DIALOGUE_CHAT_BACKEND="stub",
    TTS_BACKEND="browser",
    GEMINI_API_KEY="",
    EMBEDDING_BACKEND="hash",
)
class OfflineLocalTurnTests(TestCase):
    def setUp(self):
        reset_cache()
        self.user = User.objects.create_user(
            email="offline.local@example.com",
            password="pw-strong-123",
            role=Role.PATIENT,
        )
        ConsentLog.objects.create(
            user=self.user, scope=ConsentScope.AI_PROCESSING, granted=True
        )
        cg = User.objects.create_user(
            email="cg.offline.local@example.com", password="pw-strong-123", role=Role.CAREGIVER
        )
        CaregiverProfile.objects.create(
            user=cg,
            display_name="Offline Local CG",
            location=Point(79.86, 6.93, srid=4326),
            certifications=["First Aid"],
            specialties=["diabetes"],
            languages=["Sinhala", "English"],
            care_levels=["basic", "intermediate"],
            trust_score=0.9,
            is_active=True,
            is_approved=True,
            is_available=True,
        )
        build_index(persist=True)

    def test_sinhala_turn_records_intent_backend_and_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(SLOT_ARTIFACT_DIR=tmp, SLOT_GATED_PROMOTION=False):
                from apps.voice import slots as slots_mod

                slots_mod._ACTIVE = None
                train_slot_classifier(force=True, include_voice_intents=False)
                slots_mod._ACTIVE = None
                out = process_turn(
                    user=self.user,
                    client_text=SINHALA_DIABETES,
                    ui_language="Sinhala",
                )
        self.assertEqual(out.get("intent_backend"), "local")
        self.assertIn(out.get("intent_source"), ("slot_classifier", "stub"))
        self.assertEqual(out["intent"]["language"], "Sinhala")
        self.assertTrue(out.get("match") and out["match"].get("results"))
        self.assertEqual(out.get("match_engine"), "vehmf")


class PolicySnapshotLocalTests(SimpleTestCase):
    @override_settings(VOICE_INTENT_BACKEND="local", LOCAL_LLM_URL="", GEMINI_API_KEY="")
    def test_policy_exposes_offline_profile(self):
        snap = policy_snapshot()
        self.assertEqual(snap["intent_backend"], "local")
        self.assertEqual(snap["intent_fallback_chain"][0], "slot_classifier")
        self.assertIn("offline_profile", snap)
        self.assertFalse(snap["offline_profile"]["requires_gemini"])
