"""Reload secrets from a mounted ``.env`` without recreating the container.

Docker Compose only injects ``env_file`` at *create* time. Mounting the host
``.env`` at ``/app/.env`` and calling ``refresh_env()`` lets Gemini keys and
backend switches pick up after ``restart`` / uvicorn reload — no
``--force-recreate`` required.
"""

from __future__ import annotations

from pathlib import Path

import environ
from django.conf import settings


_ENV_CANDIDATES = (
    Path("/app/.env"),
    Path(__file__).resolve().parents[2] / ".env",  # backend/.env (rare)
    Path(__file__).resolve().parents[3] / ".env",  # repo root when not containerized
)


def refresh_env() -> Path | None:
    """Re-read the first existing ``.env`` into ``os.environ`` + settings attrs."""
    env_file = next((p for p in _ENV_CANDIDATES if p.is_file()), None)
    if env_file is None:
        return None

    environ.Env.read_env(str(env_file), overwrite=True)
    env = environ.Env()

    key = env("GEMINI_API_KEY", default="")
    model = env("GEMINI_MODEL", default="gemini-flash-lite-latest")
    settings.GEMINI_API_KEY = key
    settings.GEMINI_MODEL = model
    settings.VOICE_INTENT_BACKEND = env("VOICE_INTENT_BACKEND", default="") or (
        "gemini" if key else "stub"
    )
    settings.ASR_BACKEND = env("ASR_BACKEND", default="auto") or "auto"
    settings.DIALOGUE_CHAT_BACKEND = env("DIALOGUE_CHAT_BACKEND", default="") or (
        "gemini" if key else "stub"
    )
    settings.LOCAL_LLM_URL = env("LOCAL_LLM_URL", default="")
    return env_file
