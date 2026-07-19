from django.apps import AppConfig


class VoiceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.voice"
    label = "voice"

    def ready(self):
        # Optional warm-load so the first mic turn isn’t a multi-minute HF download.
        from django.conf import settings

        if not getattr(settings, "WHISPER_PRELOAD", False):
            return
        backend = (getattr(settings, "ASR_BACKEND", "") or "").strip()
        if backend not in ("faster_whisper", "auto", ""):
            return
        try:
            from apps.voice.asr import _get_multi_model, _get_sinhala_model

            _get_multi_model()
            if getattr(settings, "WHISPER_SINHALA_MODEL", ""):
                _get_sinhala_model()
        except Exception:
            # Never block startup on model download failures.
            import logging

            logging.getLogger(__name__).exception("WHISPER_PRELOAD failed")
