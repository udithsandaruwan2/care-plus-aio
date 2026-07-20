"""TTS router unit tests (no live Gemini / Piper / Edge)."""

from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.voice.tts import TtsResult, pack_for_api, synthesize, synthesize_espeak, synthesize_piper


class TtsRouterTests(SimpleTestCase):
    @override_settings(TTS_BACKEND="browser")
    def test_browser_backend_returns_none(self):
        out = synthesize("Hello Serah", "en-US")
        self.assertEqual(out.source, "none")
        self.assertEqual(out.audio, b"")

    @override_settings(TTS_BACKEND="piper", PIPER_BIN="", PIPER_MODEL_DIR="/tmp/missing")
    def test_piper_missing_returns_empty(self):
        out = synthesize_piper("Hello", "en-US")
        self.assertFalse(out.audio)

    def test_pack_for_api_marks_browser_when_empty(self):
        packed = pack_for_api(TtsResult(audio=b"", mime="", source="none"))
        self.assertEqual(packed["tts_source"], "browser")
        self.assertEqual(packed["reply_audio_base64"], "")

    def test_pack_for_api_encodes_audio(self):
        packed = pack_for_api(TtsResult(audio=b"abcd", mime="audio/wav", source="piper"))
        self.assertEqual(packed["tts_source"], "piper")
        self.assertTrue(packed["reply_audio_base64"])

    @override_settings(TTS_BACKEND="auto", EDGE_TTS_ENABLED=True)
    @patch("apps.voice.tts.synthesize_edge_tts")
    def test_auto_sinhala_prefers_edge_first(self, mock_edge):
        mock_edge.return_value = TtsResult(audio=b"x", mime="audio/mpeg", source="edge")
        out = synthesize("හොඳ දවසක්", "si-LK")
        self.assertEqual(out.source, "edge")
        mock_edge.assert_called_once()

    @override_settings(TTS_BACKEND="auto", EDGE_TTS_ENABLED=True)
    @patch("apps.voice.tts.synthesize_gemini_tts")
    @patch("apps.voice.tts.synthesize_edge_tts")
    def test_auto_falls_back_to_gemini_when_edge_empty(self, mock_edge, mock_gemini):
        mock_edge.return_value = TtsResult(audio=b"", mime="", source="edge")
        mock_gemini.return_value = TtsResult(audio=b"g", mime="audio/wav", source="gemini_tts")
        out = synthesize("හොඳ දවසක්", "si-LK")
        self.assertEqual(out.source, "gemini_tts")

    @override_settings(TTS_BACKEND="auto", EDGE_TTS_ENABLED=True)
    @patch("apps.voice.tts.synthesize_espeak")
    @patch("apps.voice.tts.synthesize_edge_tts")
    @patch("apps.voice.tts.synthesize_gemini_tts")
    def test_auto_falls_back_to_espeak_when_cloud_empty(self, mock_gemini, mock_edge, mock_espeak):
        mock_edge.return_value = TtsResult(audio=b"", mime="", source="edge")
        mock_gemini.return_value = TtsResult(audio=b"", mime="", source="gemini_tts")
        mock_espeak.return_value = TtsResult(audio=b"w", mime="audio/wav", source="espeak")
        out = synthesize("හොඳ දවසක්", "si-LK")
        self.assertEqual(out.source, "espeak")

    @override_settings(TTS_BACKEND="espeak")
    @patch("apps.voice.tts.shutil.which", return_value=None)
    def test_espeak_missing_returns_empty(self, _which):
        out = synthesize_espeak("hello", "si-LK")
        self.assertFalse(out.audio)
