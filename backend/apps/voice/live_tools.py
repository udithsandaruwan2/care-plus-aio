"""Gemini Live session tools + system prompt for Serah Care Plus."""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import sync_to_async

from apps.voice.dialogue import process_turn
from apps.voice.session import clear_active_sessions
from apps.voice.tts import resolve_persona

logger = logging.getLogger(__name__)

SERAH_LIVE_SYSTEM = """You are Serah, the warm Care Plus voice assistant for Sri Lanka.
You speak naturally in English, Tamil, or Sinhala to match the patient.
Never invent caregiver names, ranks, scores, or match results.
When the user asks to find a caregiver, search, rematch, refine, clarify care needs,
or book — call the serah_voice_turn tool with their utterance text.
When they want to start over / new request, call clear_voice_session.
After a tool returns, speak the reply field to the patient in their language.
Keep spoken replies concise and caring. Do not read raw JSON aloud.
"""

LIVE_TOOL_DECLARATIONS = [
    {
        "name": "serah_voice_turn",
        "description": (
            "Run Care Plus dialogue + VEHMF caregiver matching for a patient utterance. "
            "Use for care-seeking, greetings that need platform context, refine, clarify, "
            "and booking-related turns. Returns authoritative reply text and optional match cards."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Patient utterance transcript to process.",
                },
                "ui_language": {
                    "type": "string",
                    "enum": ["English", "Tamil", "Sinhala"],
                    "description": "Preferred reply language when known.",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "clear_voice_session",
        "description": "Clear the active Serah dialogue session and match cards for a new request.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


def _json_safe_match(match: dict | None) -> dict | None:
    if not match:
        return None
    results = []
    for row in match.get("results") or []:
        if not isinstance(row, dict):
            continue
        results.append(
            {
                "caregiver_id": row.get("caregiver_id"),
                "rank": row.get("rank"),
                "score": row.get("score"),
                "display_name": row.get("display_name"),
                "specialties": row.get("specialties") or [],
                "distance_m": row.get("distance_m"),
                "explanation": (row.get("explanation") or "")[:240],
                "trust_score": row.get("trust_score"),
            }
        )
    return {
        "request_id": match.get("request_id"),
        "latency_ms": match.get("latency_ms"),
        "query": match.get("query") or "",
        "emergency": bool(match.get("emergency")),
        "results": results,
    }


def run_serah_voice_turn_sync(
    *,
    user,
    text: str,
    ui_language: str | None = None,
    voice_persona: str | None = None,
    has_prior_match: bool = False,
    prior_intent: dict | None = None,
    prior_match: dict | None = None,
) -> dict[str, Any]:
    """Execute dialogue with TTS skipped (Live speaks the reply)."""
    lang = ui_language if ui_language in ("English", "Tamil", "Sinhala") else None
    result = process_turn(
        user=user,
        client_text=(text or "").strip(),
        audio=None,
        content_type=None,
        has_prior_match=has_prior_match,
        prior_intent=prior_intent,
        prior_match=prior_match,
        ui_language=lang,
        voice_persona=resolve_persona(voice_persona),
        skip_tts=True,
    )
    return {
        "ok": True,
        "route": result.get("route"),
        "situation": result.get("situation"),
        "reply": result.get("reply") or "",
        "reply_lang": result.get("reply_lang") or "",
        "transcript": result.get("transcript") or text,
        "intent": result.get("intent"),
        "match": _json_safe_match(result.get("match") if isinstance(result.get("match"), dict) else None),
        "clear_match": bool(result.get("clear_match")),
        "session_id": result.get("session_id"),
        "open_questions": result.get("open_questions") or [],
        "action": result.get("action"),
    }


def run_clear_session_sync(*, user) -> dict[str, Any]:
    clear_active_sessions(user)
    return {
        "ok": True,
        "cleared": True,
        "reply": "Ready for a fresh request. How can I help?",
    }


async def execute_live_tool(
    *,
    user,
    name: str,
    args: dict[str, Any] | None,
    ui_language: str | None,
    voice_persona: str | None,
    has_prior_match: bool,
    prior_intent: dict | None,
    prior_match: dict | None,
) -> dict[str, Any]:
    args = args or {}
    if name == "clear_voice_session":
        return await sync_to_async(run_clear_session_sync)(user=user)
    if name == "serah_voice_turn":
        text = str(args.get("text") or "").strip()
        tool_lang = args.get("ui_language") or ui_language
        if not text:
            return {"ok": False, "error": "empty_text", "reply": ""}
        return await sync_to_async(run_serah_voice_turn_sync)(
            user=user,
            text=text,
            ui_language=tool_lang,
            voice_persona=voice_persona,
            has_prior_match=has_prior_match,
            prior_intent=prior_intent,
            prior_match=prior_match,
        )
    return {"ok": False, "error": f"unknown_tool:{name}"}
