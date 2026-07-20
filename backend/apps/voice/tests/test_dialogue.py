"""Dialogue turn routing (text-only; no live Gemini in unit tests)."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import ConsentLog, ConsentScope
from apps.voice.dialogue import _route, process_turn
from apps.voice.replies import stub_for_situation

User = get_user_model()


class RouteUnitTests(TestCase):
    def test_greeting_is_chat(self):
        self.assertEqual(_route("hello there", {}, False), "CHAT")

    def test_care_need_clarify_when_incomplete(self):
        self.assertEqual(
            _route("I need a caregiver for diabetes", {"condition": "Diabetes"}, False),
            "CLARIFY",
        )

    def test_complete_intent_is_match(self):
        intent = {
            "condition": "Diabetes",
            "language": "Sinhala",
            "care_level": "intermediate",
        }
        self.assertEqual(_route("find me someone", intent, False), "MATCH")

    def test_thanks_after_match_is_chat(self):
        intent = {
            "condition": "Diabetes",
            "language": "Sinhala",
            "care_level": "basic",
        }
        self.assertEqual(_route("thank you", intent, True), "CHAT")


@override_settings(
    VOICE_INTENT_BACKEND="stub",
    ASR_BACKEND="client",
    DIALOGUE_CHAT_BACKEND="stub",
    TTS_BACKEND="browser",
)
class VoiceTurnApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="turn@example.com", password="pw-strong-123")
        ConsentLog.objects.create(
            user=self.user, scope=ConsentScope.AI_PROCESSING, granted=True
        )
        self.url = reverse("v1:voice_turn")

    def test_chat_turn_returns_reply(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(self.url, {"text": "hello"}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["route"], "CHAT")
        self.assertTrue(resp.data["reply"])
        self.assertEqual(resp.data["asr_source"], "client")
        self.assertIn("tts_source", resp.data)

    def test_process_turn_empty(self):
        out = process_turn(user=self.user, client_text="")
        self.assertEqual(out["route"], "CHAT")
        self.assertIn("catch", out["reply"].lower())

    def test_process_turn_empty_with_audio_hint(self):
        out = process_turn(
            user=self.user,
            client_text="",
            audio=b"not-real-but-present",
            content_type="audio/webm",
            ui_language="English",
        )
        self.assertIn("heard audio", out["reply"].lower())

    def test_ui_language_locks_reply_lang(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            self.url,
            {"text": "hello", "ui_language": "Sinhala"},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["reply_lang"], "si-LK")
        self.assertEqual(resp.data["intent"]["language"], "Sinhala")

    def test_asr_language_fields_present(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(self.url, {"text": "hello"}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("asr_language", resp.data)
        self.assertIn("asr_language_code", resp.data)


@override_settings(
    VOICE_INTENT_BACKEND="stub",
    ASR_BACKEND="client",
    DIALOGUE_CHAT_BACKEND="stub",
    TTS_BACKEND="browser",
)
class ProcessTurnLanguageMergeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="lang@example.com", password="pw-strong-123")

    def test_asr_hint_overrides_latin_english_chip(self):
        from apps.voice.asr import AsrResult

        fake = AsrResult(
            text="mata diabetes thiyenawa",
            source="faster_whisper",
            language_hint="Sinhala",
            language_code="si",
            languages=["Sinhala", "English"],
        )
        with patch("apps.voice.dialogue.resolve_transcript", return_value=fake):
            out = process_turn(
                user=self.user,
                client_text="mata diabetes thiyenawa",
                prior_intent={"language": "English", "languages": ["English"]},
            )
        self.assertEqual(out["intent"]["language"], "Sinhala")
        self.assertIn("Sinhala", out["intent"]["languages"])
        self.assertEqual(out["asr_language"], "Sinhala")

    def test_ui_language_wins_over_asr_hint(self):
        from apps.voice.asr import AsrResult

        fake = AsrResult(
            text="hello I need care",
            source="faster_whisper",
            language_hint="English",
            language_code="en",
            languages=["English"],
        )
        with patch("apps.voice.dialogue.resolve_transcript", return_value=fake):
            out = process_turn(
                user=self.user,
                client_text="hello I need care",
                ui_language="Tamil",
            )
        self.assertEqual(out["intent"]["language"], "Tamil")
        self.assertEqual(out["reply_lang"], "ta-LK")

    def test_thanks_after_match_does_not_rematch(self):
        from apps.voice.asr import AsrResult

        fake = AsrResult(
            text="thank you so much",
            source="client",
            language_hint="English",
            language_code="en",
            languages=["English"],
        )
        prior = {
            "condition": "diabetes",
            "language": "English",
            "care_level": "basic",
            "languages": ["English"],
        }
        with patch("apps.voice.dialogue.resolve_transcript", return_value=fake):
            out = process_turn(
                user=self.user,
                client_text="thank you so much",
                has_prior_match=True,
                prior_intent=prior,
                ui_language="English",
            )
        self.assertEqual(out["route"], "CHAT")
        self.assertEqual(out["situation"], "thanks")
        self.assertIsNone(out["match"])
        self.assertIn("welcome", out["reply"].lower())

    def test_general_condition_statement_runs_match_when_slots_complete(self):
        from apps.voice.asr import AsrResult

        fake = AsrResult(
            text="i have dengue",
            source="client",
            language_hint="English",
            language_code="en",
            languages=["English"],
        )
        prior = {
            "condition": "",
            "language": "English",
            "care_level": "basic",
            "languages": ["English"],
        }
        extracted = {
            "condition": "dengue",
            "language": "",
            "languages": [],
            "care_level": "",
            "urgency": "routine",
            "raw_text": "i have dengue",
            "source": "stub",
        }
        with (
            patch("apps.voice.dialogue.resolve_transcript", return_value=fake),
            patch("apps.voice.dialogue.extract_intent", return_value=extracted),
            patch(
                "apps.voice.dialogue._run_vehmf",
                return_value={"request_id": None, "results": [], "latency_ms": 1, "query": "dengue", "emergency": False, "cf_enabled": False, "cf_version": "", "weights": {"cbf": 1, "cf": 0, "geo": 0, "trust": 0}},
            ),
        ):
            out = process_turn(
                user=self.user,
                client_text="i have dengue",
                prior_intent=prior,
                ui_language="English",
            )
        self.assertEqual(out["route"], "MATCH")
        self.assertEqual(out["situation"], "match")


class ReplyGroundingTests(SimpleTestCase):
    def test_post_match_chat_without_results_does_not_claim_visible_cards(self):
        line = stub_for_situation("post_match_chat", "en-US", match=None)
        self.assertIn("caregiver cards right now", line.lower())

    def test_request_without_results_guides_to_browse_or_rematch(self):
        line = stub_for_situation("request", "en-US", match=None)
        self.assertIn("browse", line.lower())
        self.assertIn("fresh match", line.lower())
