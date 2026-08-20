"""Push a match payload to the patient's WebSocket group."""

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def push_match_results(user_id: int, payload: dict) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        f"match_{user_id}",
        {"type": "match.results", "payload": payload},
    )


def push_care_request_update(user_id: int, payload: dict) -> None:
    """Notify patient or caregiver of care-request lifecycle changes."""
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        f"match_{user_id}",
        {"type": "care_request.updated", "payload": payload},
    )


def push_care_relationship_update(user_id: int, payload: dict) -> None:
    """Notify patient or caregiver of care-relationship lifecycle changes."""
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        f"match_{user_id}",
        {"type": "care_relationship.updated", "payload": payload},
    )


# Stages emitted from process_turn (Step 83). Order matters for perceived latency.
TURN_STAGES = (
    "transcript",
    "intent",
    "route",
    "reply_text",
    "match",
    "reply_audio",
    "done",
)


def push_turn_stage(user_id: int, stage: str, payload: dict) -> None:
    """Push one voice-turn stage to ``ws/match/<user_id>/`` (no-op without a layer)."""
    if stage not in TURN_STAGES:
        raise ValueError(f"Unknown turn stage: {stage!r}")
    layer = get_channel_layer()
    if layer is None:
        return
    body = dict(payload or {})
    body.setdefault("stage", stage)
    async_to_sync(layer.group_send)(
        f"match_{user_id}",
        {"type": f"turn.{stage}", "payload": body},
    )
