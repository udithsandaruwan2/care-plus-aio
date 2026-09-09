"""WebSocket consumer: browser PCM ↔ Gemini Live bridge.

Clients connect to ``ws/voice/live/<user_id>/?token=<jwt>``.
"""

from __future__ import annotations

import base64
import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.cache import cache

from apps.common.envutil import voice_live_enabled
from apps.voice.live_bridge import LiveSessionRunner

logger = logging.getLogger(__name__)


class VoiceLiveConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        user_id = self.scope["url_route"]["kwargs"].get("user_id")
        if (
            user is None
            or not getattr(user, "is_authenticated", False)
            or str(user.pk) != str(user_id)
        ):
            await self.close(code=4401)
            return

        if not self._rate_ok(user.pk):
            await self.accept()
            await self.send(
                text_data=json.dumps(
                    {"type": "live.unavailable", "reason": "voice_live_rate_limit"}
                )
            )
            await self.close(code=4429)
            return

        self.user = user
        self.runner: LiveSessionRunner | None = None
        await self.accept()
        if not voice_live_enabled():
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "live.unavailable",
                        "reason": "Live disabled or missing GEMINI_VOICE_API_KEY",
                    }
                )
            )

    async def disconnect(self, code):
        runner = getattr(self, "runner", None)
        if runner:
            await runner.close()
            self.runner = None

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data and self.runner:
            await self.runner.push_pcm(bytes_data)
            return
        if not text_data:
            return
        try:
            msg = json.loads(text_data)
        except json.JSONDecodeError:
            return
        mtype = msg.get("type") or ""
        if mtype == "live.start":
            await self._start(msg)
        elif mtype == "live.audio":
            await self._audio(msg)
        elif mtype == "live.text":
            if self.runner:
                await self.runner.push_text(str(msg.get("text") or ""))
        elif mtype == "live.interrupt":
            if self.runner:
                await self.runner.interrupt()
        elif mtype == "live.end":
            if self.runner:
                await self.runner.close()
                self.runner = None
            await self.send(text_data=json.dumps({"type": "live.closed"}))

    async def _start(self, msg: dict) -> None:
        if self.runner:
            await self.runner.close()
        if not voice_live_enabled():
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "live.unavailable",
                        "reason": "Live disabled or missing GEMINI_VOICE_API_KEY",
                    }
                )
            )
            return
        self.runner = LiveSessionRunner(
            user=self.user,
            emit=self._emit,
            ui_language=msg.get("ui_language") or "English",
            voice_persona=msg.get("voice") or "female",
        )
        await self.runner.start()

    async def _audio(self, msg: dict) -> None:
        if not self.runner:
            return
        raw = msg.get("data") or ""
        try:
            pcm = base64.b64decode(raw)
        except Exception:
            return
        await self.runner.push_pcm(pcm)

    async def _emit(self, payload: dict) -> None:
        await self.send(text_data=json.dumps(payload))

    def _rate_ok(self, user_id: int) -> bool:
        from django.conf import settings

        limit = int(getattr(settings, "VOICE_LIVE_RATE_LIMIT", 60) or 0)
        window = int(getattr(settings, "VOICE_LIVE_RATE_WINDOW_SEC", 3600) or 3600)
        if limit <= 0:
            return True
        key = f"voice_live:sess:{user_id}"
        try:
            n = cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=window)
            n = 1
        return n <= limit
