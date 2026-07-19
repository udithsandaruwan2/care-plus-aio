"""Speech-to-text backends.

``client`` — browser Web Speech transcript (often English-only in Chrome).
``gemini_audio`` — multilingual transcription via Gemini (Singlish/Tanglish OK).
``faster_whisper`` — reserved local slot (empty until you wire the model).
``auto`` — prefer gemini_audio when audio + API key exist, else client text.
"""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class AsrResult:
    text: str
    source: str  # client | gemini_audio | faster_whisper | none
    language_hint: str | None = None


def transcribe_faster_whisper(audio: bytes, content_type: str) -> AsrResult:
    """Local ASR slot — not configured yet.

    Future: load ``faster-whisper`` from ``LOCAL_ASR_MODEL`` / ``ml/artifacts``.
    """
    _ = audio, content_type, settings.LOCAL_LLM_URL
    return AsrResult(text="", source="faster_whisper")


def transcribe_gemini_audio(audio: bytes, content_type: str) -> AsrResult:
    """Multilingual ASR via Gemini (handles Sinhala/Tamil/English mixes)."""
    from apps.common.envutil import refresh_env

    refresh_env()
    if not settings.GEMINI_API_KEY:
        return AsrResult(text="", source="gemini_audio")

    try:
        import google.generativeai as genai
    except ImportError:
        return AsrResult(text="", source="gemini_audio")

    suffix = {
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
    }.get(content_type.split(";")[0].strip(), ".webm")

    path: Path | None = None
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio)
            path = Path(tmp.name)

        uploaded = genai.upload_file(str(path), mime_type=content_type.split(";")[0].strip())
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        resp = model.generate_content(
            [
                (
                    "You are a Sri Lankan care-platform ASR. Transcribe the patient's speech. "
                    "They may speak Sinhala, Tamil, English, or mix (Singlish/Tanglish). "
                    "Preserve original script for Sinhala/Tamil words; keep English words in Latin. "
                    "Return ONLY JSON: "
                    '{"transcript":"...","languages":["Sinhala"|"Tamil"|"English",...]}'
                ),
                uploaded,
            ],
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.0,
            },
        )
        data = json.loads(resp.text or "{}")
        text = (data.get("transcript") or "").strip()
        langs = data.get("languages") or []
        hint = None
        for pref in ("Sinhala", "Tamil", "English"):
            if pref in langs:
                hint = pref
                break
        return AsrResult(text=text, source="gemini_audio", language_hint=hint)
    except Exception:
        logger.exception("gemini_audio ASR failed")
        return AsrResult(text="", source="gemini_audio")
    finally:
        if path is not None:
            path.unlink(missing_ok=True)


def resolve_transcript(
    *,
    client_text: str,
    audio: bytes | None,
    content_type: str | None,
) -> AsrResult:
    """Pick the best transcript for this turn."""
    from apps.common.envutil import refresh_env

    refresh_env()
    backend = (getattr(settings, "ASR_BACKEND", "auto") or "auto").strip() or "auto"
    client = (client_text or "").strip()

    if backend == "client":
        return AsrResult(text=client, source="client" if client else "none")

    if backend == "faster_whisper":
        if not audio:
            return AsrResult(text=client, source="client" if client else "none")
        result = transcribe_faster_whisper(audio, content_type or "audio/webm")
        return result if result.text else AsrResult(text=client, source="client" if client else "none")

    # auto | gemini_audio — prefer server multilingual ASR when we have audio.
    use_gemini = backend in ("auto", "gemini_audio") and bool(audio) and bool(settings.GEMINI_API_KEY)
    if use_gemini:
        result = transcribe_gemini_audio(audio or b"", content_type or "audio/webm")
        if result.text:
            return result
        # Fall back to client captions if Gemini ASR fails.
        if client:
            return AsrResult(text=client, source="client")
        return result

    return AsrResult(text=client, source="client" if client else "none")
