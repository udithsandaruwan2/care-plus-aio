"""Text-to-speech backends — Care Plus pluggable TTS.

``TTS_BACKEND``:
  - ``auto`` (default): Piper local (English when installed) → Gemini TTS → none
  - ``piper``: local Piper only
  - ``gemini_tts``: Gemini speech models only
  - ``browser`` / ``none``: skip server audio (client speechSynthesis)
"""

from __future__ import annotations

import base64
import logging
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

_BCP47 = {
    "Sinhala": "si-LK",
    "Tamil": "ta-LK",
    "English": "en-US",
    "si-LK": "si-LK",
    "ta-LK": "ta-LK",
    "en-US": "en-US",
}


@dataclass
class TtsResult:
    audio: bytes
    mime: str
    source: str  # piper | gemini_tts | none

    @property
    def audio_base64(self) -> str:
        if not self.audio:
            return ""
        return base64.b64encode(self.audio).decode("ascii")


def _empty(source: str = "none") -> TtsResult:
    return TtsResult(audio=b"", mime="", source=source)


def _pcm16_to_wav(pcm: bytes, *, sample_rate: int = 24000, channels: int = 1) -> bytes:
    """Wrap raw PCM s16le as a WAV file for browser ``Audio`` playback."""
    buf = tempfile.SpooledTemporaryFile()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    buf.seek(0)
    return buf.read()


def _looks_like_wav(data: bytes) -> bool:
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"


def synthesize_piper(text: str, lang: str) -> TtsResult:
    """Local Piper TTS when binary + English voice model are present."""
    if not text.strip():
        return _empty("piper")
    # Piper Sinhala/Tamil voices are uncommon; only attempt English locally.
    if not (lang.startswith("en") or lang == "English"):
        return _empty("piper")

    piper_bin = shutil.which("piper") or getattr(settings, "PIPER_BIN", "") or ""
    model_dir = Path(getattr(settings, "PIPER_MODEL_DIR", "") or "/ml/tts/piper")
    model = model_dir / (getattr(settings, "PIPER_EN_MODEL", "") or "en_US-lessac-medium.onnx")
    if not piper_bin or not model.is_file():
        return _empty("piper")

    out_wav = Path(tempfile.mktemp(suffix=".wav"))
    try:
        proc = subprocess.run(
            [piper_bin, "--model", str(model), "--output_file", str(out_wav)],
            input=text.encode("utf-8"),
            capture_output=True,
            check=False,
            timeout=60,
        )
        if proc.returncode != 0 or not out_wav.is_file():
            logger.warning("piper failed: %s", proc.stderr[-400:] if proc.stderr else "")
            return _empty("piper")
        data = out_wav.read_bytes()
        if not data:
            return _empty("piper")
        return TtsResult(audio=data, mime="audio/wav", source="piper")
    except Exception:
        logger.exception("piper TTS failed")
        return _empty("piper")
    finally:
        out_wav.unlink(missing_ok=True)


def synthesize_gemini_tts(text: str, lang: str) -> TtsResult:
    """Gemini TTS (supports Sinhala, Tamil, English)."""
    from apps.common.envutil import refresh_env

    refresh_env()
    if not text.strip() or not settings.GEMINI_API_KEY:
        return _empty("gemini_tts")

    model_name = (
        getattr(settings, "TTS_GEMINI_MODEL", "") or "gemini-2.5-flash-preview-tts"
    ).strip()
    voice = (getattr(settings, "TTS_GEMINI_VOICE", "") or "Kore").strip() or "Kore"

    # Prefer new google-genai SDK; fall back to REST.
    try:
        return _gemini_tts_sdk(text, lang, model_name, voice)
    except Exception:
        logger.exception("gemini TTS SDK path failed; trying REST")
    try:
        return _gemini_tts_rest(text, lang, model_name, voice)
    except Exception:
        logger.exception("gemini TTS REST failed")
        return _empty("gemini_tts")


def _prompt_for_lang(text: str, lang: str) -> str:
    if lang.startswith("si") or lang == "Sinhala":
        style = "Speak clearly in Sinhala as Serah, a warm Sri Lankan care assistant."
    elif lang.startswith("ta") or lang == "Tamil":
        style = "Speak clearly in Tamil as Serah, a warm Sri Lankan care assistant."
    else:
        style = "Speak clearly in English as Serah, a warm Sri Lankan care assistant."
    return f"{style}\n\n{text}"


def _gemini_tts_sdk(text: str, lang: str, model_name: str, voice: str) -> TtsResult:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    resp = client.models.generate_content(
        model=model_name,
        contents=_prompt_for_lang(text, lang),
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )
    data = b""
    mime = "audio/wav"
    try:
        part = resp.candidates[0].content.parts[0]
        inline = part.inline_data
        raw = inline.data
        if isinstance(raw, str):
            data = base64.b64decode(raw)
        else:
            data = bytes(raw or b"")
        mime = (inline.mime_type or mime).split(";")[0].strip() or mime
    except Exception:
        return _empty("gemini_tts")

    if not data:
        return _empty("gemini_tts")
    if _looks_like_wav(data):
        return TtsResult(audio=data, mime="audio/wav", source="gemini_tts")
    # Gemini often returns raw PCM s16le @ 24 kHz.
    wav = _pcm16_to_wav(data, sample_rate=24000)
    return TtsResult(audio=wav, mime="audio/wav", source="gemini_tts")


def _gemini_tts_rest(text: str, lang: str, model_name: str, voice: str) -> TtsResult:
    import json
    import urllib.error
    import urllib.request

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
    )
    body = {
        "contents": [{"parts": [{"text": _prompt_for_lang(text, lang)}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}},
            },
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    try:
        part = payload["candidates"][0]["content"]["parts"][0]["inlineData"]
        raw_b64 = part.get("data") or ""
        mime = (part.get("mimeType") or "audio/wav").split(";")[0].strip()
        data = base64.b64decode(raw_b64)
    except (KeyError, IndexError, TypeError):
        return _empty("gemini_tts")
    if not data:
        return _empty("gemini_tts")
    if _looks_like_wav(data) or mime == "audio/wav":
        return TtsResult(audio=data, mime="audio/wav", source="gemini_tts")
    return TtsResult(audio=_pcm16_to_wav(data), mime="audio/wav", source="gemini_tts")


def synthesize(text: str, reply_lang: str) -> TtsResult:
    """Route TTS per ``TTS_BACKEND``."""
    backend = (getattr(settings, "TTS_BACKEND", "auto") or "auto").strip().lower()
    lang = _BCP47.get(reply_lang, reply_lang) or "en-US"

    if backend in ("browser", "none", ""):
        return _empty("none")

    if backend == "piper":
        return synthesize_piper(text, lang)

    if backend == "gemini_tts":
        return synthesize_gemini_tts(text, lang)

    # auto: piper (en) → gemini → none (browser fallback)
    if lang.startswith("en"):
        local = synthesize_piper(text, lang)
        if local.audio:
            return local
    cloud = synthesize_gemini_tts(text, lang)
    if cloud.audio:
        return cloud
    return _empty("none")


def pack_for_api(result: TtsResult) -> dict:
    return {
        "reply_audio_base64": result.audio_base64,
        "reply_audio_mime": result.mime if result.audio else "",
        "tts_source": result.source if result.audio else "browser",
    }
