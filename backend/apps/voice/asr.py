"""Speech-to-text backends — Care Plus local-first ASR (no Gemini by default).

Pipeline:
  1. Decode browser audio → 16 kHz mono WAV (ffmpeg)
  2. Multilingual Whisper: ``detect_language`` (fast)
  3. Route:
     - Sinhala (or en/hi mis-tag) → SPEAK-ASR Sinhala specialist
     - Tamil → multilingual forced ``ta``
     - English / other → multilingual auto
  4. Browser captions are last resort only (English-biased)

``ASR_BACKEND=gemini_audio`` remains available as an optional override.
"""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

_WHISPER_LOCK = threading.Lock()
_MULTI_MODEL = None
_SI_MODEL = None

_SINHALA_RE = re.compile(r"[\u0D80-\u0DFF]")
_TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")

# ISO → Care Plus labels.
_ISO_TO_LABEL = {
    "si": "Sinhala",
    "ta": "Tamil",
    "en": "English",
    "hi": "English",  # common false positive for Sinhala
}

# Care-domain priming helps Whisper stay on medical vocabulary.
_INITIAL_PROMPT = (
    "Care Plus Sri Lanka. Conditions: diabetes දියවැඩියා, dengue ඩෙංගු, "
    "asthma ඇදුම, heart රෝග. Languages: Sinhala සිංහල, Tamil தமிழ், English. "
    "Care levels: basic, intermediate, advanced. Caregiver match request."
)


@dataclass
class AsrResult:
    text: str
    source: str  # client | gemini_audio | faster_whisper | none
    language_hint: str | None = None
    language_code: str | None = None
    languages: list[str] = field(default_factory=list)
    confidence: float | None = None


def _ffmpeg_to_wav(audio: bytes, content_type: str) -> Path:
    """Decode browser webm/ogg/mp4 → 16 kHz mono WAV for Whisper."""
    suffix = {
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
    }.get((content_type or "").split(";")[0].strip(), ".webm")

    raw = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    raw.write(audio)
    raw.close()
    wav = Path(tempfile.mktemp(suffix=".wav"))
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                raw.name,
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(wav),
            ],
            check=True,
            capture_output=True,
        )
    finally:
        Path(raw.name).unlink(missing_ok=True)
    return wav


def _download_root() -> str | None:
    root = getattr(settings, "WHISPER_DOWNLOAD_ROOT", "") or None
    return root


def _get_multi_model():
    global _MULTI_MODEL
    if _MULTI_MODEL is not None:
        return _MULTI_MODEL
    with _WHISPER_LOCK:
        if _MULTI_MODEL is not None:
            return _MULTI_MODEL
        from faster_whisper import WhisperModel

        name = getattr(settings, "WHISPER_MODEL", "small") or "small"
        device = getattr(settings, "WHISPER_DEVICE", "cpu") or "cpu"
        compute = getattr(settings, "WHISPER_COMPUTE_TYPE", "int8") or "int8"
        logger.info("Loading multilingual Whisper %s (%s/%s)", name, device, compute)
        _MULTI_MODEL = WhisperModel(
            name,
            device=device,
            compute_type=compute,
            download_root=_download_root(),
        )
        return _MULTI_MODEL


def _get_sinhala_model():
    """SPEAK-ASR Sinhala specialist (falls back to multilingual if unset/unavailable)."""
    global _SI_MODEL
    si_name = (getattr(settings, "WHISPER_SINHALA_MODEL", "") or "").strip()
    if not si_name:
        return _get_multi_model()
    if _SI_MODEL is not None:
        return _SI_MODEL
    with _WHISPER_LOCK:
        if _SI_MODEL is not None:
            return _SI_MODEL
        from faster_whisper import WhisperModel

        device = getattr(settings, "WHISPER_DEVICE", "cpu") or "cpu"
        # SPEAK CT2 weights are float16; on CPU prefer int8, else float32.
        compute = getattr(settings, "WHISPER_SINHALA_COMPUTE_TYPE", "") or ""
        if not compute:
            compute = "int8" if device == "cpu" else "float16"
        try:
            logger.info("Loading Sinhala Whisper %s (%s/%s)", si_name, device, compute)
            _SI_MODEL = WhisperModel(
                si_name,
                device=device,
                compute_type=compute,
                download_root=_download_root(),
            )
        except Exception:
            logger.exception("Sinhala model load failed; using multilingual")
            _SI_MODEL = _get_multi_model()
        return _SI_MODEL


def _detect_language(wav: Path) -> tuple[str | None, float]:
    """Fast language ID via multilingual encoder (no full decode)."""
    import numpy as np
    from faster_whisper.audio import decode_audio

    model = _get_multi_model()
    audio = decode_audio(str(wav), sampling_rate=16000)
    # detect_language expects a float32 waveform
    if not isinstance(audio, np.ndarray):
        audio = np.asarray(audio, dtype=np.float32)
    lang, prob, _all = model.detect_language(audio)
    return (lang or None), float(prob or 0.0)


def _transcribe(
    model,
    wav: Path,
    *,
    language: str | None,
) -> tuple[str, str | None, float]:
    segments, info = model.transcribe(
        str(wav),
        language=language,
        task="transcribe",
        beam_size=3,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,
        without_timestamps=True,
        initial_prompt=_INITIAL_PROMPT,
    )
    parts: list[str] = []
    probs: list[float] = []
    for seg in segments:
        t = (seg.text or "").strip()
        if t:
            parts.append(t)
            if seg.avg_logprob is not None:
                probs.append(float(seg.avg_logprob))
    text = " ".join(parts).strip()
    code = getattr(info, "language", None) or language
    conf = max(probs) if probs else float(getattr(info, "language_probability", 0.0) or 0.0)
    return text, code, conf


def _label_from_code(code: str | None) -> str | None:
    if not code:
        return None
    return _ISO_TO_LABEL.get(code.lower())


def _script_languages(text: str) -> list[str]:
    from apps.voice.extraction import detect_languages

    # Always plain str labels for JSON / chips.
    return [str(x) for x in detect_languages(text)]


def _route_language(detected: str | None, prob: float) -> tuple[str, str | None]:
    """Returns (route, forced_iso) where route is si|ta|multi."""
    code = (detected or "").lower()
    if code == "si":
        return "si", "si"
    if code == "ta":
        return "ta", "ta"
    # Hindi/Urdu/Bengali tags are common false positives for Sinhala speech.
    if code in ("hi", "ur", "bn", ""):
        return "si", "si"
    # Uncertain English → try Sinhala specialist (Sri Lanka primary).
    if code == "en" and prob < 0.75:
        return "si", "si"
    if not code or prob < 0.5:
        return "si", "si"
    return "multi", code or None


_UI_TO_ISO = {
    "Sinhala": "si",
    "Tamil": "ta",
    "English": "en",
}


def _ui_to_iso(ui_language: str | None) -> str | None:
    if not ui_language:
        return None
    return _UI_TO_ISO.get(ui_language.strip())


def transcribe_faster_whisper(
    audio: bytes,
    content_type: str,
    *,
    ui_language: str | None = None,
) -> AsrResult:
    """Local multilingual ASR; ``ui_language`` forces si/ta/en (skips detect)."""
    if not audio:
        return AsrResult(text="", source="faster_whisper")

    wav: Path | None = None
    try:
        wav = _ffmpeg_to_wav(audio, content_type)
        forced_ui = _ui_to_iso(ui_language)
        if forced_ui:
            route = "si" if forced_ui == "si" else ("ta" if forced_ui == "ta" else "multi")
            forced = forced_ui
            detected, prob = forced_ui, 1.0
            logger.info("ASR ui_language=%s route=%s forced=%s", ui_language, route, forced)
        else:
            detected, prob = _detect_language(wav)
            route, forced = _route_language(detected, prob)
            logger.info(
                "ASR route=%s detected=%s (%.2f) forced=%s",
                route,
                detected,
                prob,
                forced,
            )

        if route == "si":
            text, code, score = _transcribe(_get_sinhala_model(), wav, language="si")
            if not text:
                text, code, score = _transcribe(_get_multi_model(), wav, language="si")
        elif route == "ta":
            text, code, score = _transcribe(_get_multi_model(), wav, language="ta")
        else:
            text, code, score = _transcribe(_get_multi_model(), wav, language=forced or "en")

        if not text:
            return AsrResult(text="", source="faster_whisper")

        langs = _script_languages(text)
        hint = (
            ui_language
            if ui_language in ("Sinhala", "Tamil", "English")
            else (_label_from_code(code) or _label_from_code(forced) or _label_from_code(detected))
        )
        if route == "si" and "Sinhala" not in langs and _SINHALA_RE.search(text):
            langs.insert(0, "Sinhala")
        if hint and hint not in langs:
            langs = [hint, *[x for x in langs if x != hint]]
        if not hint and langs:
            hint = langs[0]

        return AsrResult(
            text=text,
            source="faster_whisper",
            language_hint=hint,
            language_code=code or forced or detected,
            languages=langs,
            confidence=score,
        )
    except Exception:
        logger.exception("faster_whisper ASR failed")
        return AsrResult(text="", source="faster_whisper")
    finally:
        if wav is not None:
            wav.unlink(missing_ok=True)


def transcribe_gemini_audio(audio: bytes, content_type: str) -> AsrResult:
    """Optional Gemini ASR — only when ASR_BACKEND=gemini_audio (not default)."""
    from apps.common.envutil import refresh_env

    refresh_env()
    if not settings.GEMINI_API_KEY:
        return AsrResult(text="", source="gemini_audio")

    try:
        import json
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
    }.get((content_type or "").split(";")[0].strip(), ".webm")

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
        langs = [x for x in (data.get("languages") or []) if x in ("Sinhala", "Tamil", "English")]
        hint = None
        for pref in ("Sinhala", "Tamil", "English"):
            if pref in langs:
                hint = pref
                break
        return AsrResult(text=text, source="gemini_audio", language_hint=hint, languages=langs)
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
    ui_language: str | None = None,
) -> AsrResult:
    """Pick the best transcript for this turn — local Whisper first."""
    from apps.common.envutil import refresh_env

    refresh_env()
    backend = (getattr(settings, "ASR_BACKEND", "faster_whisper") or "faster_whisper").strip()
    if not backend or backend == "auto":
        backend = "faster_whisper"
    client = (client_text or "").strip()
    ui = ui_language if ui_language in ("Sinhala", "Tamil", "English") else None

    if backend == "client":
        hint = ui
        langs = [ui] if ui else []
        return AsrResult(
            text=client,
            source="client" if client else "none",
            language_hint=hint,
            language_code=_ui_to_iso(ui),
            languages=langs,
        )

    if backend == "gemini_audio":
        if audio:
            result = transcribe_gemini_audio(audio, content_type or "audio/webm")
            if result.text:
                if ui:
                    result.language_hint = ui
                    if ui not in result.languages:
                        result.languages = [ui, *result.languages]
                return result
        return AsrResult(
            text=client,
            source="client" if client else "none",
            language_hint=ui,
            language_code=_ui_to_iso(ui),
            languages=[ui] if ui else [],
        )

    # faster_whisper (default) — never prefer English browser captions over audio.
    if audio:
        result = transcribe_faster_whisper(
            audio, content_type or "audio/webm", ui_language=ui
        )
        if result.text:
            return result
        logger.warning("faster_whisper returned empty; falling back to client captions")
    return AsrResult(
        text=client,
        source="client" if client else "none",
        language_hint=ui,
        language_code=_ui_to_iso(ui),
        languages=[ui] if ui else [],
    )
