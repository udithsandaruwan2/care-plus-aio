"""Push message events to WebSocket subscribers."""

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def _group_name(thread_id: int) -> str:
    return f"message_thread_{thread_id}"


def push_message_created(thread_id: int, payload: dict) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        _group_name(thread_id),
        {"type": "message.created", "payload": payload},
    )


def push_messages_read(thread_id: int, payload: dict) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        _group_name(thread_id),
        {"type": "message.read", "payload": payload},
    )
