"""WebSocket consumer for match result push (Step 20).

Clients connect to ``ws/match/<user_id>/?token=<jwt>``. After ``POST /match/``
the API also broadcasts the same payload to this group so the UI can update
live (and later emergency re-matches can push without a new HTTP round-trip).
"""

from __future__ import annotations

import json

from channels.generic.websocket import AsyncWebsocketConsumer


class MatchConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        patient_id = self.scope["url_route"]["kwargs"].get("patient_id")
        if (
            user is None
            or not getattr(user, "is_authenticated", False)
            or str(user.pk) != str(patient_id)
        ):
            await self.close(code=4401)
            return

        self.group = f"match_{user.pk}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.send(
            text_data=json.dumps({"type": "match.ready", "patient_id": user.pk})
        )

    async def disconnect(self, code):
        group = getattr(self, "group", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def match_results(self, event):
        """Handler for ``group_send(..., {"type": "match.results", ...})``."""
        await self.send(
            text_data=json.dumps({"type": "match.results", "payload": event["payload"]})
        )

    async def care_request_updated(self, event):
        """Handler for care-request accept/reject/create notifications."""
        await self.send(
            text_data=json.dumps(
                {"type": "care_request.updated", "payload": event["payload"]}
            )
        )

    async def care_relationship_updated(self, event):
        await self.send(
            text_data=json.dumps(
                {"type": "care_relationship.updated", "payload": event["payload"]}
            )
        )
