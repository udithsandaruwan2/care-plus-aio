"""Dialogue AI policy — backends, rate limits, and locked VEHMF split (Step 15j).

Locked rules:
  - CHAT / clarify copy may use Gemini or stub (``DIALOGUE_CHAT_BACKEND``).
  - MATCH / REFINE ranking is **always** local VEHMF — never Gemini-picked IDs.
  - Without ``GEMINI_API_KEY``, chat falls back to stub; matching still works.
"""

from __future__ import annotations

import logging
import time

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Redis key prefix for Gemini chat rate limiting.
_RATE_KEY = "careplus:dialogue:gemini:{user_id}"


def resolve_chat_backend() -> str:
    """Return ``stub``, ``gemini``, or ``local`` for Serah chat (never for ranking).

    Does not reload ``.env`` — callers (``VoiceTurnView``) already call
    ``refresh_env()`` so Django ``override_settings`` in tests keeps working.
    """
    raw = (getattr(settings, "DIALOGUE_CHAT_BACKEND", "") or "").strip().lower()
    local_url = bool((getattr(settings, "LOCAL_LLM_URL", "") or "").strip())
    if raw == "local":
        return "local" if local_url else "stub"
    if raw in ("stub", "gemini"):
        if raw == "gemini" and not settings.GEMINI_API_KEY:
            return "stub"
        return raw
    # Blank: prefer Gemini when keyed; else local LLM URL; else stub.
    if settings.GEMINI_API_KEY:
        return "gemini"
    if local_url:
        return "local"
    return "stub"


def gemini_chat_allowed(user_id: int | None) -> tuple[bool, str]:
    """Rate-limit Gemini chat per user. Returns (allowed, reason).

    reason is ``ok``, ``no_user``, ``disabled``, or ``rate_limited``.
    """
    if resolve_chat_backend() != "gemini":
        return False, "disabled"
    if user_id is None:
        return True, "ok"  # anonymous/tests without user still gated by key

    limit = int(getattr(settings, "DIALOGUE_GEMINI_RATE_LIMIT", 120) or 120)
    window = int(getattr(settings, "DIALOGUE_GEMINI_RATE_WINDOW_SEC", 3600) or 3600)
    if limit <= 0:
        return False, "disabled"

    key = _RATE_KEY.format(user_id=user_id)
    try:
        # Sliding window via sorted set of timestamps (cache backend may be Redis).
        now = time.time()
        pipe_data = cache.get(key)
        stamps: list[float]
        if isinstance(pipe_data, list):
            stamps = [float(t) for t in pipe_data if now - float(t) < window]
        else:
            stamps = []
        if len(stamps) >= limit:
            return False, "rate_limited"
        stamps.append(now)
        cache.set(key, stamps, timeout=window)
        return True, "ok"
    except Exception:
        logger.exception("Gemini chat rate-limit cache failed; allowing request")
        return True, "ok"


def policy_snapshot() -> dict:
    """Public/debug summary of the dialogue AI split."""
    intent_backend = (getattr(settings, "VOICE_INTENT_BACKEND", "") or "").strip().lower() or "auto"
    local_url = bool((getattr(settings, "LOCAL_LLM_URL", "") or "").strip())
    return {
        "chat_backend": resolve_chat_backend(),
        "intent_backend": intent_backend,
        "intent_fallback_chain": ["slot_classifier", "gemini", "stub"],
        "local_llm_configured": local_url,
        "match_engine": "vehmf",
        "gemini_ranks_caregivers": False,
        "offline_profile": {
            "voice_intent_backend": "local",
            "dialogue_chat_backend": "stub",
            "requires_gemini": False,
            "notes": (
                "Train/promote a slot classifier, set VOICE_INTENT_BACKEND=local, "
                "DIALOGUE_CHAT_BACKEND=stub, GEMINI_API_KEY unset. Matching stays VEHMF."
            ),
        },
        "gemini_rate_limit": int(getattr(settings, "DIALOGUE_GEMINI_RATE_LIMIT", 120) or 120),
        "gemini_rate_window_sec": int(
            getattr(settings, "DIALOGUE_GEMINI_RATE_WINDOW_SEC", 3600) or 3600
        ),
        "has_gemini_key": bool(settings.GEMINI_API_KEY),
    }
