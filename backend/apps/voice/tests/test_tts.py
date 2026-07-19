"""TTS router unit tests (no live Gemini / Piper)."""

from django.test import SimpleTestCase, override_settings

from apps.voice.tts import TtsResult, pack_for_api, synthesize, synthesize_piper


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
