"""Intent NLP backends: stub | gemini | local (empty slot)."""

from __future__ import annotations

from django.conf import settings

from .extraction import extract_gemini, extract_stub


def extract_local(text: str, hint_language: str | None = None) -> dict:
    """On-prem / local LLM slot — wire ``LOCAL_LLM_URL`` later.

    Until configured, returns the deterministic stub tagged ``local_unconfigured``
    so the pipeline stays usable offline.
    """
    out = extract_stub(text, hint_language)
    url = getattr(settings, "LOCAL_LLM_URL", "") or ""
    if not url:
        out["source"] = "local_unconfigured"
        return out
    # Future: POST {text} → LOCAL_LLM_URL and map to Care Plus schema.
    out["source"] = "local_unconfigured"
    return out


def extract_intent(text: str, hint_language: str | None = None) -> dict:
    from apps.common.envutil import refresh_env

    refresh_env()
    backend = (getattr(settings, "VOICE_INTENT_BACKEND", "") or "").strip()
    if not backend:
        backend = "gemini" if settings.GEMINI_API_KEY else "stub"
    if backend == "local":
        return extract_local(text, hint_language)
    if backend == "gemini" and settings.GEMINI_API_KEY:
        return extract_gemini(text, hint_language)
    return extract_stub(text, hint_language)
