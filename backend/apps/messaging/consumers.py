"""WebSocket consumer for in-app messaging (Step 38)."""

from __future__ import annotations

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .services import can_access_thread, get_thread_for_user


class MessageConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        thread_id = self.scope["url_route"]["kwargs"].get("thread_id")
        if user is None or not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return

        try:
            thread = await database_sync_to_async(get_thread_for_user)(user, int(thread_id))
        except Exception:
            await self.close(code=4403)
            return

        self.thread_id = thread.pk
        self.group = f"message_thread_{self.thread_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.send(
            text_data=json.dumps(
                {"type": "message.ready", "thread_id": self.thread_id}
            )
        )

    async def disconnect(self, code):
        group = getattr(self, "group", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def message_created(self, event):
        await self.send(
            text_data=json.dumps({"type": "message.created", "payload": event["payload"]})
        )

    async def message_read(self, event):
        await self.send(
            text_data=json.dumps({"type": "message.read", "payload": event["payload"]})
        )
