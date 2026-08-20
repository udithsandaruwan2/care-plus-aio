"""Step 84 — TTS phrase cache + first_text timing."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from apps.voice.tts import (
    TtsResult,
    phrase_cache_stats,
    synthesize,
)
from apps.voice.dialogue import process_turn
from django.contrib.auth import get_user_model

from apps.accounts.models import Role

User = get_user_model()


@override_settings(
    TTS_BACKEND="espeak",
    TTS_PHRASE_CACHE=True,
    TTS_DEFER_UNCACHED=False,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class PhraseCacheTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("apps.voice.tts._synthesize_uncached")
    def test_second_call_is_cache_hit(self, mock_uncached):
        mock_uncached.return_value = TtsResult(audio=b"wavdata", mime="audio/wav", source="espeak")
        a = synthesize("Finding your best match…", "en-US")
        b = synthesize("Finding your best match…", "en-US")
        self.assertEqual(a.audio, b"wavdata")
        self.assertIn("cache", b.source)
        self.assertEqual(mock_uncached.call_count, 1)
        stats = phrase_cache_stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertGreaterEqual(stats["hit_rate"], 0.5)

    @patch("apps.voice.tts._synthesize_uncached")
    def test_scripted_five_turn_hit_rate_above_60(self, mock_uncached):
        """Canned clarify / finding lines repeat → >60% hits across five turns."""
        mock_uncached.return_value = TtsResult(audio=b"x", mime="audio/wav", source="espeak")
        phrases = [
            "Tell me a bit more so I can find the right caregiver.",
            "I'm finding one for you. We can keep chatting while I search.",
            "Tell me a bit more so I can find the right caregiver.",
            "I'm finding one for you. We can keep chatting while I search.",
            "Tell me a bit more so I can find the right caregiver.",
        ]
        for p in phrases:
            synthesize(p, "en-US")
        stats = phrase_cache_stats()
        # 2 unique → 2 misses + 3 hits = 60%
        self.assertGreaterEqual(stats["hit_rate"], 0.6)
        self.assertEqual(stats["hits"] + stats["misses"], 5)


@override_settings(
    VOICE_INTENT_BACKEND="stub",
    ASR_BACKEND="client",
    DIALOGUE_CHAT_BACKEND="stub",
    TTS_BACKEND="browser",
    TTS_PHRASE_CACHE=True,
    TTS_DEFER_UNCACHED=True,
)
class FirstTextTimingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="tts.first@example.com", password="pw-strong-123", role=Role.PATIENT
        )

    def test_first_text_ms_excludes_waiting_on_tts(self):
        out = process_turn(user=self.user, client_text="hello", ui_language="English")
        timings = out["timings"]
        self.assertIn("first_text_ms", timings)
        self.assertGreaterEqual(timings["first_text_ms"], 0)
        # With browser TTS, tts span is cheap; first_text should be <= total.
        self.assertLessEqual(timings["first_text_ms"], timings["total_ms"])
