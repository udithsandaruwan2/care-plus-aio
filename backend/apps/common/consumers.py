"""WebSocket consumers.

PingConsumer is a connectivity smoke test for the Channels/ASGI stack. Feature
channels (ws/match, ws/alerts) are added in later milestones.
"""

import json

from channels.generic.websocket import AsyncWebsocketConsumer


class PingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send(text_data=json.dumps({"type": "welcome", "message": "pong-ready"}))

    async def receive(self, text_data=None, bytes_data=None):
        # Echo whatever we receive so clients can verify the round-trip.
        await self.send(text_data=json.dumps({"type": "echo", "data": text_data}))

    async def disconnect(self, code):
        pass
