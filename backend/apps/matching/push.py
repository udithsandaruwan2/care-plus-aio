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
