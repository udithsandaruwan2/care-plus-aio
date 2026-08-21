"""Intent NLP backends: local slot classifier | gemini | stub (Step 97).

Fallback chain (``VOICE_INTENT_BACKEND=auto`` or blank)::

    local classifier → Gemini → stub

``local`` skips Gemini (fully offline). ``gemini`` / ``stub`` pin a single backend.
Each result includes ``source`` and ``fallback_reason`` for turn telemetry.
"""

from __future__ import annotations

from django.conf import settings

from .extraction import extract_gemini, extract_stub


def _annotate(out: dict, *, backend: str, fallback_reason: str = "") -> dict:
    out = dict(out)
    out.setdefault("raw_text", out.get("raw_text") or "")
    out["intent_backend"] = backend
    out["fallback_reason"] = fallback_reason or ""
    return out


def _try_slot_classifier(text: str, hint_language: str | None) -> dict | None:
    try:
        from .slots import extract_with_classifier, load_slot_classifier
    except Exception:
        return None
    clf = load_slot_classifier()
    if clf is None:
        return None
    out = extract_with_classifier(text, hint_language, classifier=clf)
    if not out:
        return None
    out["source"] = "slot_classifier"
    return out


def extract_local(text: str, hint_language: str | None = None) -> dict:
    """Offline / on-prem intent: Step 96 classifier, then stub (never Gemini)."""
    classified = _try_slot_classifier(text, hint_language)
    if classified is not None:
        return _annotate(classified, backend="local", fallback_reason="")
    stub = extract_stub(text, hint_language)
    stub["source"] = "stub"
    return _annotate(stub, backend="local", fallback_reason="no_active_slot_classifier")


def _try_gemini(text: str, hint_language: str | None) -> tuple[dict | None, str]:
    if not getattr(settings, "GEMINI_API_KEY", ""):
        return None, "no_gemini_key"
    try:
        out = extract_gemini(text, hint_language)
    except Exception:
        return None, "gemini_error"
    if out.get("source") == "gemini":
        return out, ""
    # extract_gemini returns stub-shaped dict on soft failure
    return None, "gemini_unavailable"


def extract_intent(text: str, hint_language: str | None = None) -> dict:
    """Resolve slots via configured backend + documented fallback chain."""
    from apps.common.envutil import refresh_env

    refresh_env()
    backend = (getattr(settings, "VOICE_INTENT_BACKEND", "") or "").strip().lower()
    if not backend:
        backend = "auto"

    if backend == "stub":
        return _annotate(extract_stub(text, hint_language), backend="stub")

    if backend == "local":
        return extract_local(text, hint_language)

    if backend == "gemini":
        gemini_out, reason = _try_gemini(text, hint_language)
        if gemini_out is not None:
            return _annotate(gemini_out, backend="gemini")
        stub = extract_stub(text, hint_language)
        stub["source"] = "stub"
        return _annotate(stub, backend="gemini", fallback_reason=reason or "gemini_unavailable")

    # auto (default): local classifier → Gemini → stub
    classified = _try_slot_classifier(text, hint_language)
    if classified is not None:
        return _annotate(classified, backend="auto", fallback_reason="")

    gemini_out, reason = _try_gemini(text, hint_language)
    if gemini_out is not None:
        return _annotate(
            gemini_out,
            backend="auto",
            fallback_reason="no_active_slot_classifier",
        )

    stub = extract_stub(text, hint_language)
    stub["source"] = "stub"
    parts = ["no_active_slot_classifier"]
    if reason:
        parts.append(reason)
    return _annotate(stub, backend="auto", fallback_reason="+".join(parts))
