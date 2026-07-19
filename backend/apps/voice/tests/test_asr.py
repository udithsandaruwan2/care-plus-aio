"""Local faster-whisper ASR routing + Sri Lanka language preference."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.voice.asr import AsrResult, resolve_transcript, transcribe_faster_whisper


class ResolveTranscriptTests(SimpleTestCase):
    @override_settings(ASR_BACKEND="client")
    def test_client_backend_uses_captions(self):
        out = resolve_transcript(client_text="hello", audio=b"x", content_type="audio/webm")
        self.assertEqual(out.text, "hello")
        self.assertEqual(out.source, "client")

    @override_settings(ASR_BACKEND="faster_whisper")
    def test_prefers_whisper_over_english_captions(self):
        fake = AsrResult(
            text="මට දියවැඩියා තියෙනවා",
            source="faster_whisper",
            language_hint="Sinhala",
            language_code="si",
            languages=["Sinhala"],
        )
        with patch("apps.voice.asr.transcribe_faster_whisper", return_value=fake):
            out = resolve_transcript(
                client_text="harsingar ka jagran",
                audio=b"fake-webm",
                content_type="audio/webm",
            )
        self.assertEqual(out.source, "faster_whisper")
        self.assertIn("දියවැඩියා", out.text)
        self.assertEqual(out.language_hint, "Sinhala")

    @override_settings(ASR_BACKEND="auto")
    def test_auto_maps_to_faster_whisper(self):
        fake = AsrResult(text="ok", source="faster_whisper", language_hint="English")
        with patch("apps.voice.asr.transcribe_faster_whisper", return_value=fake):
            out = resolve_transcript(client_text="x", audio=b"a", content_type="audio/webm")
        self.assertEqual(out.source, "faster_whisper")


class WhisperRouteTests(SimpleTestCase):
    @override_settings(
        ASR_BACKEND="faster_whisper",
        WHISPER_MODEL="tiny",
        WHISPER_SINHALA_MODEL="fake-si",
        WHISPER_DEVICE="cpu",
        WHISPER_COMPUTE_TYPE="int8",
        WHISPER_DOWNLOAD_ROOT="/tmp/whisper-test",
    )
    def test_routes_suspicious_english_to_sinhala_model(self):
        wav = MagicMock()
        wav.unlink = MagicMock()
        multi = MagicMock()
        si_model = MagicMock()

        with (
            patch("apps.voice.asr._ffmpeg_to_wav", return_value=wav),
            patch("apps.voice.asr._detect_language", return_value=("en", 0.4)),
            patch("apps.voice.asr._get_multi_model", return_value=multi),
            patch("apps.voice.asr._get_sinhala_model", return_value=si_model),
            patch(
                "apps.voice.asr._transcribe",
                return_value=("මට දියවැඩියා තියෙනවා", "si", -0.2),
            ) as tr,
        ):
            out = transcribe_faster_whisper(b"audio", "audio/webm")

        self.assertEqual(out.language_hint, "Sinhala")
        self.assertIn("දියවැඩියා", out.text)
        # Called with Sinhala specialist, forced si
        self.assertEqual(tr.call_args.args[0], si_model)
        self.assertEqual(tr.call_args.kwargs.get("language"), "si")

    @override_settings(
        ASR_BACKEND="faster_whisper",
        WHISPER_MODEL="tiny",
        WHISPER_SINHALA_MODEL="",
        WHISPER_DEVICE="cpu",
        WHISPER_COMPUTE_TYPE="int8",
    )
    def test_routes_tamil_to_multilingual(self):
        wav = MagicMock()
        wav.unlink = MagicMock()
        multi = MagicMock()

        with (
            patch("apps.voice.asr._ffmpeg_to_wav", return_value=wav),
            patch("apps.voice.asr._detect_language", return_value=("ta", 0.9)),
            patch("apps.voice.asr._get_multi_model", return_value=multi),
            patch(
                "apps.voice.asr._transcribe",
                return_value=("எனக்கு நீரிழிவு உள்ளது", "ta", -0.1),
            ) as tr,
        ):
            out = transcribe_faster_whisper(b"audio", "audio/webm")

        self.assertEqual(out.language_hint, "Tamil")
        self.assertEqual(tr.call_args.kwargs.get("language"), "ta")

    @override_settings(
        ASR_BACKEND="faster_whisper",
        WHISPER_MODEL="tiny",
        WHISPER_SINHALA_MODEL="fake-si",
        WHISPER_DEVICE="cpu",
        WHISPER_COMPUTE_TYPE="int8",
    )
    def test_ui_language_skips_detect_and_forces_si(self):
        wav = MagicMock()
        wav.unlink = MagicMock()
        si_model = MagicMock()

        with (
            patch("apps.voice.asr._ffmpeg_to_wav", return_value=wav),
            patch("apps.voice.asr._detect_language") as detect,
            patch("apps.voice.asr._get_sinhala_model", return_value=si_model),
            patch(
                "apps.voice.asr._transcribe",
                return_value=("මට දියවැඩියා තියෙනවා", "si", -0.2),
            ) as tr,
        ):
            out = transcribe_faster_whisper(
                b"audio", "audio/webm", ui_language="Sinhala"
            )

        detect.assert_not_called()
        self.assertEqual(out.language_hint, "Sinhala")
        self.assertEqual(tr.call_args.kwargs.get("language"), "si")
