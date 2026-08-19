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

    def test_care_need_with_condition_is_match(self):
        self.assertEqual(
            _route("I need a caregiver for diabetes", {"condition": "Diabetes"}, False),
            "MATCH",
        )

    def test_care_seek_without_condition_clarifies(self):
        self.assertEqual(_route("find me a caregiver", {}, False), "CLARIFY")

    def test_complete_intent_is_match(self):
        intent = {
            "condition": "Diabetes",
            "language": "Sinhala",
            "care_level": "intermediate",
        }
        self.assertEqual(_route("find me a caregiver", intent, False), "MATCH")

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
        ConsentLog.objects.create(user=self.user, scope=ConsentScope.AI_PROCESSING, granted=True)
        self.url = reverse("v1:voice_turn")

    def test_chat_turn_returns_reply(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(self.url, {"text": "hello"}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["route"], "CHAT")
        self.assertTrue(resp.data["reply"])
        self.assertEqual(resp.data["asr_source"], "client")
        self.assertIn("tts_source", resp.data)
        timings = resp.data["timings"]
        self.assertIn("asr_ms", timings)
        self.assertIn("intent_ms", timings)
        self.assertIn("route_ms", timings)
        self.assertIn("match_ms", timings)
        self.assertIn("chat_ms", timings)
        self.assertIn("tts_ms", timings)
        self.assertIn("total_ms", timings)
        stage_sum = (
            timings["asr_ms"]
            + timings["intent_ms"]
            + timings["route_ms"]
            + timings["match_ms"]
            + timings["chat_ms"]
            + timings["tts_ms"]
        )
        self.assertLessEqual(abs(stage_sum - timings["total_ms"]), 50)

    def test_turn_timings_echo_request_id(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            self.url,
            {"text": "hello"},
            format="multipart",
            HTTP_X_REQUEST_ID="rid-step77",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp["X-Request-ID"], "rid-step77")
        self.assertEqual(resp.data["timings"]["request_id"], "rid-step77")
        from apps.voice.models import VoiceTurnTiming

        row = VoiceTurnTiming.objects.get(request_id="rid-step77")
        self.assertEqual(row.route, "CHAT")
        self.assertGreaterEqual(row.total_ms, 0)

    def test_process_turn_empty(self):
        out = process_turn(user=self.user, client_text="")
        self.assertEqual(out["route"], "CHAT")
        self.assertEqual(out["situation"], "empty")
        self.assertTrue(out.get("silent"))
        self.assertEqual(out["reply"], "")
        self.assertIn("timings", out)
        self.assertGreaterEqual(out["timings"]["total_ms"], 0)

    def test_process_turn_empty_with_audio_hint(self):
        out = process_turn(
            user=self.user,
            client_text="",
            audio=b"not-real-but-present",
            content_type="audio/webm",
            ui_language="English",
        )
        self.assertTrue(out.get("silent"))
        self.assertEqual(out["reply"], "")
        self.assertNotIn("heard audio", out["reply"].lower())

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

    def test_condition_statement_stays_chat_until_care_seek(self):
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
            patch("apps.voice.dialogue.extract_stub", return_value=extracted),
            patch("apps.voice.dialogue.extract_intent") as intent_gemini,
        ):
            out = process_turn(
                user=self.user,
                client_text="i have dengue",
                prior_intent=prior,
                ui_language="English",
            )
        self.assertEqual(out["route"], "CHAT")
        self.assertEqual(out["situation"], "general")
        self.assertIsNone(out["match"])
        intent_gemini.assert_not_called()
        self.assertEqual(out["tts_source"], "browser")

    def test_explicit_care_seek_after_condition_runs_match(self):
        from apps.voice.asr import AsrResult

        fake = AsrResult(
            text="find me a caregiver",
            source="client",
            language_hint="English",
            language_code="en",
            languages=["English"],
        )
        prior = {
            "condition": "dengue",
            "language": "English",
            "care_level": "basic",
            "languages": ["English"],
        }
        with (
            patch("apps.voice.dialogue.resolve_transcript", return_value=fake),
            patch(
                "apps.voice.dialogue._run_vehmf",
                return_value={
                    "request_id": None,
                    "results": [],
                    "latency_ms": 1,
                    "query": "dengue",
                    "emergency": False,
                    "cf_enabled": False,
                    "cf_version": "",
                    "weights": {"cbf": 1, "cf": 0, "geo": 0, "trust": 0},
                },
            ) as vehmf,
        ):
            out = process_turn(
                user=self.user,
                client_text="find me a caregiver",
                prior_intent=prior,
                ui_language="English",
            )
        self.assertEqual(out["route"], "MATCH")
        vehmf.assert_called_once()

    def test_gemini_vehmf_promise_still_runs_match(self):
        from apps.voice.asr import AsrResult

        fake = AsrResult(
            text="please go ahead",
            source="client",
            language_hint="English",
            language_code="en",
            languages=["English"],
        )
        prior = {
            "condition": "dengue",
            "language": "English",
            "care_level": "basic",
            "languages": ["English"],
        }
        with (
            patch("apps.voice.dialogue.resolve_transcript", return_value=fake),
            patch(
                "apps.voice.dialogue._serah",
                return_value=(
                    "I'm on it! I'll let you know the moment VEHMF finishes matching "
                    "and the results are ready to show on your screen.",
                    "gemini",
                ),
            ),
            patch(
                "apps.voice.dialogue._run_vehmf",
                return_value={
                    "request_id": None,
                    "results": [
                        {
                            "display_name": "Nimal Perera",
                            "score": 0.8,
                            "explanation": "Matched because: strong medical/skill match.",
                        }
                    ],
                    "latency_ms": 1,
                    "query": "dengue",
                    "emergency": False,
                    "cf_enabled": False,
                    "cf_version": "",
                    "weights": {"cbf": 1, "cf": 0, "geo": 0, "trust": 0},
                },
            ) as vehmf,
        ):
            out = process_turn(
                user=self.user,
                client_text="please go ahead",
                prior_intent=prior,
                ui_language="English",
            )
        self.assertEqual(out["route"], "MATCH")
        self.assertIsNotNone(out["match"])
        vehmf.assert_called_once()
        self.assertNotIn("I'll let you know", out["reply"])

    def test_search_going_promise_runs_match_without_condition(self):
        from apps.voice.asr import AsrResult

        fake = AsrResult(
            text="okay then",
            source="client",
            language_hint="English",
            language_code="en",
            languages=["English"],
        )
        prior = {
            "language": "English",
            "care_level": "intermediate",
            "languages": ["English"],
        }
        with (
            patch("apps.voice.dialogue.resolve_transcript", return_value=fake),
            patch(
                "apps.voice.dialogue._serah",
                return_value=(
                    "Great, let's get that search going for you in Colombo right away! "
                    "Could you share any specific care requirements or preferences?",
                    "gemini",
                ),
            ),
            patch(
                "apps.voice.dialogue._run_vehmf",
                return_value={
                    "request_id": None,
                    "results": [{"display_name": "Nimal Perera", "score": 0.8, "explanation": ""}],
                    "latency_ms": 1,
                    "query": "",
                    "emergency": False,
                    "cf_enabled": False,
                    "cf_version": "",
                    "weights": {"cbf": 1, "cf": 0, "geo": 0, "trust": 0},
                },
            ) as vehmf,
        ):
            out = process_turn(
                user=self.user,
                client_text="okay then",
                prior_intent=prior,
                ui_language="English",
            )
        self.assertEqual(out["route"], "MATCH")
        self.assertIsNotNone(out["match"])
        vehmf.assert_called_once()

    def test_english_chat_skips_server_tts(self):
        with patch("apps.voice.tts.synthesize") as syn:
            out = process_turn(
                user=self.user,
                client_text="hello",
                ui_language="English",
            )
        syn.assert_not_called()
        self.assertEqual(out["tts_source"], "browser")

    @override_settings(TTS_BACKEND="auto")
    def test_sinhala_chat_attaches_server_audio(self):
        from apps.voice.tts import TtsResult

        with patch(
            "apps.voice.tts.synthesize",
            return_value=TtsResult(audio=b"abcd", mime="audio/mpeg", source="edge"),
        ):
            out = process_turn(
                user=self.user,
                client_text="හායි",
                ui_language="Sinhala",
            )
        self.assertEqual(out["reply_lang"], "si-LK")
        self.assertEqual(out["tts_source"], "edge")
        self.assertTrue(out["reply_audio_base64"])

    def test_ui_picker_locks_spoken_lang_not_caregiver_chip(self):
        out = process_turn(
            user=self.user,
            client_text="hello",
            ui_language="Sinhala",
            prior_intent={"language": "English", "languages": ["English"]},
        )
        self.assertEqual(out["reply_lang"], "si-LK")


class ReplyGroundingTests(SimpleTestCase):
    def test_post_match_chat_without_results_does_not_claim_visible_cards(self):
        line = stub_for_situation("post_match_chat", "en-US", match=None)
        self.assertIn("caregiver cards right now", line.lower())

    def test_request_without_results_guides_to_browse_or_rematch(self):
        line = stub_for_situation("request", "en-US", match=None)
        self.assertIn("browse", line.lower())
        self.assertIn("fresh match", line.lower())
