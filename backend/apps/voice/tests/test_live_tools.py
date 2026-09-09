"""Unit tests for Live tools (no real Gemini)."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.voice.live_tools import run_clear_session_sync, run_serah_voice_turn_sync

User = get_user_model()


@override_settings(TTS_BACKEND="browser", DIALOGUE_CHAT_BACKEND="stub")
class LiveToolsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="live.patient@careplus.local",
            password="x",
            role="patient",
        )

    @patch("apps.voice.live_tools.process_turn")
    def test_voice_turn_tool_skips_tts_path(self, mock_turn):
        mock_turn.return_value = {
            "route": "CHAT",
            "situation": "greeting",
            "reply": "Hi, I’m Serah.",
            "reply_lang": "en-US",
            "transcript": "hi",
            "intent": None,
            "match": None,
            "clear_match": False,
            "session_id": 1,
            "open_questions": [],
            "action": None,
        }
        out = run_serah_voice_turn_sync(user=self.user, text="hi", ui_language="English")
        self.assertTrue(out["ok"])
        self.assertEqual(out["reply"], "Hi, I’m Serah.")
        kwargs = mock_turn.call_args.kwargs
        self.assertTrue(kwargs["skip_tts"])
        self.assertEqual(kwargs["client_text"], "hi")

    def test_clear_session_tool(self):
        out = run_clear_session_sync(user=self.user)
        self.assertTrue(out["ok"])
        self.assertTrue(out["cleared"])
