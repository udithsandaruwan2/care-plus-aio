"""Text-to-speech backends — Care Plus pluggable TTS.

``TTS_BACKEND``:
  - ``auto`` (default): Edge neural → Gemini TTS → Piper (English) → espeak → none
  - ``piper``: local Piper only
  - ``gemini_tts``: Gemini speech models only
  - ``edge``: Microsoft Edge neural voices (Sinhala/Tamil/English, no API key)
  - ``espeak``: local espeak-ng (offline, robotic)
  - ``browser`` / ``none``: skip server audio (client speechSynthesis)
"""

from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import hashlib
import json
import logging
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Redis keys for phrase-cache hit-rate (Step 84).
_CACHE_HITS_KEY = "tts:phrase:hits"
_CACHE_MISSES_KEY = "tts:phrase:misses"
_CACHE_TTL_SEC = 60 * 60 * 24 * 7  # one week for canned Serah lines

_BCP47 = {
    "Sinhala": "si-LK",
    "Tamil": "ta-LK",
    "English": "en-US",
    "si-LK": "si-LK",
    "ta-LK": "ta-LK",
    "en-US": "en-US",
}

#: Voice personas a patient can choose between. Serah defaults to the warm
#: female voice; the male alternative exists for households that prefer it.
VOICE_PERSONAS = ("female", "male")
DEFAULT_PERSONA = "female"

# Microsoft Edge neural voices (edge-tts) — strong Sinhala/Tamil without Gemini quota.
_EDGE_VOICES = {
    "si-LK": {"female": "si-LK-ThiliniNeural", "male": "si-LK-SameeraNeural"},
    "ta-LK": {"female": "ta-LK-SaranyaNeural", "male": "ta-LK-KumarNeural"},
    "en-US": {"female": "en-US-AriaNeural", "male": "en-US-GuyNeural"},
}

# Gemini prebuilt voices, matched to the same two personas.
_GEMINI_VOICES = {"female": "Kore", "male": "Puck"}


def resolve_persona(persona: str | None) -> str:
    """Coerce a client-supplied persona to one we have voices for."""
    name = (persona or "").strip().lower()
    if name in VOICE_PERSONAS:
        return name
    configured = (getattr(settings, "TTS_VOICE_PERSONA", "") or "").strip().lower()
    return configured if configured in VOICE_PERSONAS else DEFAULT_PERSONA

_ESPEAK_LANG = {
    "si-LK": "si",
    "si": "si",
    "Sinhala": "si",
    "ta-LK": "ta",
    "ta": "ta",
    "Tamil": "ta",
    "en-US": "en",
    "en": "en",
    "English": "en",
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


def synthesize_gemini_tts(text: str, lang: str, persona: str | None = None) -> TtsResult:
    """Gemini TTS (supports Sinhala, Tamil, English)."""
    from apps.common.envutil import refresh_env

    refresh_env()
    if not text.strip() or not settings.GEMINI_API_KEY:
        return _empty("gemini_tts")

    model_name = (
        getattr(settings, "TTS_GEMINI_MODEL", "") or "gemini-2.5-flash-preview-tts"
    ).strip()
    voice = _gemini_voice(persona)

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


def _gemini_voice(persona: str | None = None) -> str:
    name = resolve_persona(persona)
    if name == DEFAULT_PERSONA:
        # TTS_GEMINI_VOICE stays authoritative for deployments that pinned one.
        configured = (getattr(settings, "TTS_GEMINI_VOICE", "") or "").strip()
        if configured:
            return configured
    return _GEMINI_VOICES[name]


def _edge_voice(lang: str, persona: str | None = None) -> str:
    bcp = _BCP47.get(lang, lang) or "en-US"
    voices = _EDGE_VOICES.get(bcp) or _EDGE_VOICES["en-US"]
    return voices[resolve_persona(persona)]


def _run_coroutine(factory, timeout: float = 60):
    """Run an async factory from sync Django, including under uvicorn's loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(factory())).result(timeout=timeout)


def synthesize_edge_tts(text: str, lang: str, persona: str | None = None) -> TtsResult:
    """Microsoft Edge neural TTS — Sinhala/Tamil/English without Gemini quota."""
    if not text.strip():
        return _empty("edge")
    if not getattr(settings, "EDGE_TTS_ENABLED", True):
        return _empty("edge")
    try:
        import edge_tts
    except ImportError:
        logger.warning("edge-tts not installed")
        return _empty("edge")

    voice = _edge_voice(lang, persona)

    async def _stream() -> bytes:
        communicate = edge_tts.Communicate(text, voice)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    try:
        audio = _run_coroutine(_stream)
    except Exception:
        logger.exception("edge-tts failed")
        return _empty("edge")
    if not audio:
        return _empty("edge")
    return TtsResult(audio=audio, mime="audio/mpeg", source="edge")


def synthesize_espeak(text: str, lang: str) -> TtsResult:
    """Offline espeak-ng fallback (robotic but always available in Docker)."""
    if not text.strip():
        return _empty("espeak")
    espeak = shutil.which("espeak-ng") or getattr(settings, "ESPEAK_BIN", "") or ""
    if not espeak:
        return _empty("espeak")
    bcp = _BCP47.get(lang, lang) or "en-US"
    es_lang = _ESPEAK_LANG.get(lang) or _ESPEAK_LANG.get(bcp) or "en"
    out_wav = Path(tempfile.mktemp(suffix=".wav"))
    try:
        proc = subprocess.run(
            [espeak, "-v", es_lang, "-w", str(out_wav), text],
            capture_output=True,
            check=False,
            timeout=60,
        )
        if proc.returncode != 0 or not out_wav.is_file():
            logger.warning("espeak-ng failed: %s", proc.stderr[-300:] if proc.stderr else "")
            return _empty("espeak")
        data = out_wav.read_bytes()
        if not data:
            return _empty("espeak")
        return TtsResult(audio=data, mime="audio/wav", source="espeak")
    except Exception:
        logger.exception("espeak-ng TTS failed")
        return _empty("espeak")
    finally:
        out_wav.unlink(missing_ok=True)


def _cache_voice(persona: str | None = None) -> str:
    """Cache identity for a phrase — personas must not share cached audio."""
    return resolve_persona(persona)


def phrase_cache_key(text: str, lang: str, *, voice: str | None = None) -> str:
    voice_name = voice or _cache_voice()
    digest = hashlib.sha256(
        f"{text.strip()}\0{lang}\0{voice_name}".encode("utf-8")
    ).hexdigest()
    return f"tts:phrase:{digest}"


def phrase_cache_stats() -> dict:
    """Return hit/miss counters and rate (best-effort; zeros if Redis unavailable)."""
    try:
        hits = int(cache.get(_CACHE_HITS_KEY) or 0)
        misses = int(cache.get(_CACHE_MISSES_KEY) or 0)
    except Exception:
        return {"hits": 0, "misses": 0, "hit_rate": 0.0}
    total = hits + misses
    rate = (hits / total) if total else 0.0
    return {"hits": hits, "misses": misses, "hit_rate": round(rate, 4)}


def _bump_cache_counter(key: str) -> None:
    try:
        # django RedisCache supports incr; locmem may not — fall back to get/set.
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, None)
        except Exception:
            n = int(cache.get(key) or 0) + 1
            cache.set(key, n, None)
    except Exception:
        logger.debug("tts phrase cache counter bump failed", exc_info=True)


def _log_cache_event(*, hit: bool) -> None:
    stats = phrase_cache_stats()
    logger.info(
        "tts.phrase_cache",
        extra={
            "hit": hit,
            "hits": stats["hits"],
            "misses": stats["misses"],
            "hit_rate": stats["hit_rate"],
        },
    )


def lookup_phrase_cache(
    text: str, reply_lang: str, persona: str | None = None
) -> TtsResult | None:
    if not text.strip():
        return None
    if not getattr(settings, "TTS_PHRASE_CACHE", True):
        return None
    lang = _BCP47.get(reply_lang, reply_lang) or "en-US"
    key = phrase_cache_key(text, lang, voice=_cache_voice(persona))
    try:
        raw = cache.get(key)
    except Exception:
        logger.debug("tts phrase cache get failed", exc_info=True)
        return None
    if not raw:
        return None
    try:
        if isinstance(raw, (bytes, str)):
            payload = json.loads(raw)
        else:
            payload = raw
        audio = base64.b64decode(payload.get("audio_b64") or "")
        if not audio:
            return None
        _bump_cache_counter(_CACHE_HITS_KEY)
        _log_cache_event(hit=True)
        source = str(payload.get("source") or "cache")
        if not source.endswith("+cache"):
            source = f"{source}+cache"
        return TtsResult(audio=audio, mime=str(payload.get("mime") or "audio/wav"), source=source)
    except Exception:
        logger.debug("tts phrase cache decode failed", exc_info=True)
        return None


def store_phrase_cache(
    text: str, reply_lang: str, result: TtsResult, persona: str | None = None
) -> None:
    if not result.audio or not text.strip():
        return
    if not getattr(settings, "TTS_PHRASE_CACHE", True):
        return
    lang = _BCP47.get(reply_lang, reply_lang) or "en-US"
    key = phrase_cache_key(text, lang, voice=_cache_voice(persona))
    body = {
        "audio_b64": result.audio_base64,
        "mime": result.mime,
        "source": result.source,
    }
    try:
        cache.set(key, body, _CACHE_TTL_SEC)
    except Exception:
        logger.debug("tts phrase cache set failed", exc_info=True)


def synthesize(text: str, reply_lang: str, persona: str | None = None) -> TtsResult:
    """Route TTS per ``TTS_BACKEND``, with Redis phrase cache (Step 84)."""
    backend = (getattr(settings, "TTS_BACKEND", "auto") or "auto").strip().lower()
    if backend in ("browser", "none", ""):
        return _empty("none")

    cached = lookup_phrase_cache(text, reply_lang, persona)
    if cached is not None:
        return cached

    _bump_cache_counter(_CACHE_MISSES_KEY)
    _log_cache_event(hit=False)
    result = _synthesize_uncached(text, reply_lang, persona)
    if result.audio:
        store_phrase_cache(text, reply_lang, result, persona)
    return result


def _synthesize_uncached(text: str, reply_lang: str, persona: str | None = None) -> TtsResult:
    """Route TTS per ``TTS_BACKEND`` (no cache)."""
    backend = (getattr(settings, "TTS_BACKEND", "auto") or "auto").strip().lower()
    lang = _BCP47.get(reply_lang, reply_lang) or "en-US"

    if backend in ("browser", "none", ""):
        return _empty("none")

    if backend == "piper":
        return synthesize_piper(text, lang)

    if backend == "gemini_tts":
        return synthesize_gemini_tts(text, lang, persona)

    if backend == "edge":
        return synthesize_edge_tts(text, lang, persona)

    if backend == "espeak":
        return synthesize_espeak(text, lang)

    # auto: Edge neural first everywhere. Piper only has one English voice, so it
    # cannot honour a persona choice and now sits behind Edge rather than ahead.
    neural = synthesize_edge_tts(text, lang, persona)
    if neural.audio:
        return neural
    cloud = synthesize_gemini_tts(text, lang, persona)
    if cloud.audio:
        return cloud
    if lang.startswith("en"):
        local = synthesize_piper(text, lang)
        if local.audio:
            return local
    offline = synthesize_espeak(text, lang)
    if offline.audio:
        return offline
    return _empty("none")


def pack_for_api(result: TtsResult) -> dict:
    return {
        "reply_audio_base64": result.audio_base64,
        "reply_audio_mime": result.mime if result.audio else "",
        "tts_source": result.source if result.audio else "browser",
    }
