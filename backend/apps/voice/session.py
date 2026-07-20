"""DialogueSession helpers — get/update/clear multi-turn memory (Step 15g)."""

from __future__ import annotations

from datetime import datetime, timezone

from django.utils.timezone import now

from .models import (
    DIALOGUE_ROUTE_HISTORY_LIMIT,
    DIALOGUE_TURN_LIMIT,
    DialogueSession,
)


def open_questions_for_intent(intent: dict) -> list[str]:
    """Goal Ring slots still missing — drives clarify continuity."""
    missing: list[str] = []
    if not (intent.get("condition") or "").strip():
        missing.append("condition")
    if not (intent.get("language") or "").strip():
        missing.append("language")
    if not (intent.get("care_level") or "").strip():
        missing.append("care_level")
    return missing


def get_or_create_active_session(user, *, lang: str = "") -> DialogueSession:
    session = (
        DialogueSession.objects.filter(user=user, active=True)
        .select_related("last_match_run")
        .order_by("-updated_at")
        .first()
    )
    if session is None:
        return DialogueSession.objects.create(user=user, lang=lang or "", active=True)
    if lang and session.lang != lang:
        session.lang = lang
        session.save(update_fields=["lang", "updated_at"])
    return session


def clear_active_sessions(user) -> int:
    """Deactivate all active sessions for the user (New request). Returns count."""
    qs = DialogueSession.objects.filter(user=user, active=True)
    count = qs.count()
    if count:
        qs.update(
            active=False,
            last_match_run=None,
            intent_chips={},
            open_questions=[],
            updated_at=now(),
        )
    return count


def append_turn(
    session: DialogueSession,
    *,
    role: str,
    text: str,
    route: str,
    situation: str,
) -> None:
    turns = list(session.turns or [])
    turns.append(
        {
            "role": role,
            "text": (text or "")[:500],
            "route": route,
            "situation": situation or "",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    )
    session.turns = turns[-DIALOGUE_TURN_LIMIT:]


def append_route(session: DialogueSession, route: str, situation: str) -> None:
    history = list(session.route_history or [])
    history.append({"route": route, "situation": situation or ""})
    session.route_history = history[-DIALOGUE_ROUTE_HISTORY_LIMIT:]


def persist_session_after_turn(
    session: DialogueSession,
    *,
    intent: dict | None,
    route: str,
    situation: str,
    user_text: str,
    reply: str,
    match_run_id: int | None,
    clear_match: bool,
) -> DialogueSession:
    """Update chips, history, turns, and last MatchRun after a turn."""
    if intent:
        chips = {
            "condition": intent.get("condition") or "",
            "language": intent.get("language") or "",
            "languages": intent.get("languages") or [],
            "care_level": intent.get("care_level") or "",
            "urgency": intent.get("urgency") or "routine",
        }
        session.intent_chips = chips
        session.open_questions = open_questions_for_intent(chips)
        if chips.get("language"):
            session.lang = chips["language"]

    append_route(session, route, situation)
    append_turn(session, role="user", text=user_text, route=route, situation=situation)
    if reply:
        append_turn(session, role="serah", text=reply, route=route, situation=situation)

    if clear_match:
        session.last_match_run_id = None
    elif match_run_id:
        session.last_match_run_id = match_run_id

    session.save()
    return session
