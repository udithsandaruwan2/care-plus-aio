"""Gemini Live session tools + system prompt for Serah Care Plus."""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import sync_to_async

from apps.voice.dialogue import process_turn
from apps.voice.extraction import bcp47_to_ui
from apps.voice.session import clear_active_sessions
from apps.voice.tts import resolve_persona

logger = logging.getLogger(__name__)

SERAH_LIVE_SYSTEM = """You are Serah, the warm Care Plus voice assistant for Sri Lanka.
Never invent caregiver names, ranks, scores, or match results.
When the user asks to find a caregiver, search, rematch, refine, clarify care needs,
view a profile, send a care request, schedule a visit, book, greet, or small-talk —
call the serah_voice_turn tool with their utterance text.
Do not ask follow-up questions for "view profile", "show the profile",
"book the caregiver", "send the request", or "show the schedule" — call the
tool immediately so the side card can open.
When they want to start over / new request, call clear_voice_session.
After a tool returns, speak ONLY the reply field in speak_language.
If speak_language is Sinhala, the entire spoken reply must be Sinhala sounds.
If speak_language is Tamil, the entire spoken reply must be Tamil sounds.
If you caption a greeting as Hello / Hi / Hey alone, that is often Sinhala හායි
or ආයුබෝවන් — still speak Sinhala when the session language is Sinhala.
If they say a real English sentence ("Hi, how are you?", "I need a caregiver"),
speak English and call the tool. Mixed Singlish such as "request karan",
"kenek onee", or "my name is Kenava request karan" is a care request —
call serah_voice_turn immediately; do not ignore it.
Do not add an English translation after a Sinhala or Tamil line.
Keep spoken replies concise and caring. Do not read raw JSON aloud.
"""


def live_reply_language(ui_language: str | None) -> str:
    """How Serah should hear and pronounce a turn.

    Native audio models pick the spoken language themselves. A language code
    on the voice config is ignored, so the instruction has to say it.
    """
    lang = ui_language if ui_language in ("English", "Tamil", "Sinhala") else "English"
    return (
        f"This voice session is in {lang}. Speak {lang} from the first word. "
        f"Hear {lang} even when the caption is written in English letters. "
        "If the session is Sinhala and the caption is only Hello or Hi, reply in Sinhala "
        "(ආයුබෝවන් / හායි) — do not greet in English. "
        "If the session is Tamil and the caption is only Hello or Hi, reply in Tamil "
        "(வணக்கம்) — do not greet in English. "
        "If they say a real English sentence such as Hi, how are you? — reply in English. "
        "Switch to Sinhala or Tamil when they use those letters or romanized words "
        "(request karan, kenek, ayubowan, vanakkam). "
        "Pronounce English with English sounds, Tamil with Tamil sounds, "
        "and Sinhala with Sinhala sounds. "
        "Do not pronounce Tamil or Sinhala as if they were English."
    )

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


def _factor_breakdown(raw: object | None) -> dict[str, float]:
    src = raw if isinstance(raw, dict) else {}
    out: dict[str, float] = {}
    for key in ("cbf", "cf", "geo", "trust"):
        try:
            out[key] = float(src.get(key) or 0.0)
        except (TypeError, ValueError):
            out[key] = 0.0
    return out


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
                "breakdown": _factor_breakdown(row.get("breakdown")),
                "display_name": row.get("display_name") or "",
                "specialties": row.get("specialties") or [],
                "languages": row.get("languages") or [],
                "care_levels": row.get("care_levels") or [],
                "distance_m": row.get("distance_m"),
                "explanation": (row.get("explanation") or "")[:240],
                "trust_score": row.get("trust_score"),
                "is_available": bool(row.get("is_available", True)),
                "photo_url": row.get("photo_url"),
                "age": row.get("age"),
                "previous_rank": row.get("previous_rank"),
                "rank_delta": row.get("rank_delta"),
                "was_exploratory": bool(row.get("was_exploratory", False)),
            }
        )
    return {
        "request_id": match.get("request_id"),
        "latency_ms": match.get("latency_ms") or 0,
        "query": match.get("query") or "",
        "emergency": bool(match.get("emergency")),
        "weights": _factor_breakdown(match.get("weights")),
        "refined": bool(match.get("refined")),
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
    reply_lang = result.get("reply_lang") or ""
    speak = bcp47_to_ui(reply_lang) or lang or "English"
    return {
        "ok": True,
        "route": result.get("route"),
        "situation": result.get("situation"),
        "reply": result.get("reply") or "",
        "reply_lang": reply_lang,
        "speak_language": speak,
        "speak_instruction": (
            f"Speak the reply field verbatim in {speak}. "
            "Do not translate it into another language."
        ),
        "transcript": result.get("transcript") or text,
        "intent": result.get("intent"),
        "match": _json_safe_match(result.get("match") if isinstance(result.get("match"), dict) else None),
        "clear_match": bool(result.get("clear_match")),
        "session_id": result.get("session_id"),
        "open_questions": result.get("open_questions") or [],
        "action": result.get("action"),
    }


def run_clear_session_sync(*, user, ui_language: str | None = None) -> dict[str, Any]:
    clear_active_sessions(user)
    lang = ui_language if ui_language in ("English", "Tamil", "Sinhala") else "English"
    if lang == "Sinhala":
        reply = "හරි, අලුත් request එකකට සූදානම්. කොහොමද උදව් කරන්නේ?"
    elif lang == "Tamil":
        reply = "சரி, புதிய கோரிக்கைக்கு தயார். எப்படி உதவட்டும்?"
    else:
        reply = "Ready for a fresh request. How can I help?"
    return {
        "ok": True,
        "cleared": True,
        "reply": reply,
        "reply_lang": {"Sinhala": "si-LK", "Tamil": "ta-LK"}.get(lang, "en-US"),
        "speak_language": lang,
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
        return await sync_to_async(run_clear_session_sync)(user=user, ui_language=ui_language)
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
