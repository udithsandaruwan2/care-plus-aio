"""User-facing match history trail (Step 104).

Serializes MatchRun + results (stored XAI), linked VoiceIntent, best-effort
DialogueSession, and CareRequest outcomes. Soft-delete scrubs PHI text and
sets deleted_at so entries vanish from the API and privacy export while
AuditLog RUN_MATCH rows remain.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.accounts.audit import record_audit
from apps.accounts.models import AuditAction
from apps.matching.models import MatchRun
from apps.voice.dialogue import _match_payload_from_run


def history_queryset(*, user):
    return (
        MatchRun.objects.filter(user=user, deleted_at__isnull=True)
        .select_related("voice_intent")
        .prefetch_related(
            "results__caregiver",
            "care_requests__caregiver",
            "dialogue_sessions",
        )
        .order_by("-created_at")
    )


def serialize_history_entry(run: MatchRun) -> dict[str, Any]:
    match_payload = _match_payload_from_run(run)
    understood = None
    intent = run.voice_intent
    if intent is not None:
        understood = {
            "voice_intent_id": intent.pk,
            "raw_text": intent.raw_text,
            "condition": intent.condition,
            "language": intent.language,
            "languages": list(intent.languages or []),
            "care_level": intent.care_level,
            "urgency": intent.urgency,
            "source": intent.source,
        }

    session = None
    dlg = next(iter(run.dialogue_sessions.all()), None)
    if dlg is not None:
        session = {
            "id": dlg.pk,
            "active": dlg.active,
            "lang": dlg.lang,
            "turns": list(dlg.turns or [])[-12:],
            "intent_chips": dlg.intent_chips or {},
            "updated_at": dlg.updated_at.isoformat() if dlg.updated_at else None,
        }

    outcomes = []
    for req in run.care_requests.all():
        cg = req.caregiver
        outcomes.append(
            {
                "care_request_id": req.pk,
                "status": req.status,
                "caregiver_id": req.caregiver_id,
                "caregiver_name": cg.display_name if cg else "",
                "created_at": req.created_at.isoformat() if req.created_at else None,
            }
        )

    return {
        "id": run.pk,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "query": run.query,
        "condition": run.condition,
        "language": run.language,
        "care_level": run.care_level,
        "emergency": run.emergency,
        "latency_ms": run.latency_ms,
        "weights": list(run.weights or []),
        "understood": understood,
        "session": session,
        "results": match_payload.get("results") or [],
        "outcomes": outcomes,
    }


def soft_delete_match_run(*, run: MatchRun, user, request=None) -> MatchRun:
    """Scrub PHI fields and mark deleted; audit row is append-only."""
    if run.deleted_at is not None:
        return run
    run.query = ""
    run.condition = ""
    run.deleted_at = timezone.now()
    run.save(update_fields=["query_ciphertext", "condition_ciphertext", "deleted_at"])
    record_audit(
        actor=user,
        action=AuditAction.DELETE_MATCH_HISTORY,
        request=request,
        target_type="match_run",
        target_id=run.pk,
        metadata={"scrubbed": True},
        async_=False,
    )
    return run
