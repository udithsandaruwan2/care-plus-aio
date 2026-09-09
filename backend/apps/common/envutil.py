"""Reload Gemini secrets from a mounted ``.env`` without recreating the container.

Docker Compose only injects ``env_file`` at *create* time. Mounting the host
``.env`` at ``/app/.env`` and calling ``refresh_env()`` picks up key/model
changes after ``restart`` — no ``--force-recreate`` required.

Backend switches (``VOICE_INTENT_BACKEND``, etc.) are read at process start from
settings / env; they are **not** overwritten here so Django ``override_settings``
in tests keeps working.
"""

from __future__ import annotations

from pathlib import Path

import environ
from django.conf import settings


_ENV_CANDIDATES = (
    Path("/app/.env"),
    Path(__file__).resolve().parents[2] / ".env",
    Path(__file__).resolve().parents[3] / ".env",
)


def refresh_env() -> Path | None:
    """Re-read Gemini credentials from the first existing ``.env``."""
    env_file = next((p for p in _ENV_CANDIDATES if p.is_file()), None)
    if env_file is None:
        return None

    environ.Env.read_env(str(env_file), overwrite=True)
    env = environ.Env()
    settings.GEMINI_API_KEY = env("GEMINI_API_KEY", default="")
    settings.GEMINI_VOICE_API_KEY = env("GEMINI_VOICE_API_KEY", default="")
    settings.GEMINI_MODEL = env("GEMINI_MODEL", default=settings.GEMINI_MODEL)
    settings.TTS_GEMINI_MODEL = env(
        "TTS_GEMINI_MODEL", default=getattr(settings, "TTS_GEMINI_MODEL", "")
    )
    settings.VOICE_LIVE_MODEL = env(
        "VOICE_LIVE_MODEL", default=getattr(settings, "VOICE_LIVE_MODEL", "")
    )
    settings.VOICE_LIVE_ENABLED = env.bool(
        "VOICE_LIVE_ENABLED",
        default=getattr(settings, "VOICE_LIVE_ENABLED", True),
    )
    return env_file


def gemini_voice_api_key() -> str:
    """API key for Live + Gemini TTS (+ optional gemini_audio). Falls back to chat key."""
    voice = (getattr(settings, "GEMINI_VOICE_API_KEY", "") or "").strip()
    if voice:
        return voice
    return (getattr(settings, "GEMINI_API_KEY", "") or "").strip()


def gemini_chat_api_key() -> str:
    """API key for chat / intent only (keep quota isolated from voice when possible)."""
    return (getattr(settings, "GEMINI_API_KEY", "") or "").strip()


def voice_live_enabled() -> bool:
    """True when Live bridge may open (flag on + a usable voice/chat key)."""
    refresh_env()
    if not bool(getattr(settings, "VOICE_LIVE_ENABLED", True)):
        return False
    return bool(gemini_voice_api_key())
