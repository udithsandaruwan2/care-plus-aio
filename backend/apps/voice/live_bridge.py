"""Server-side Gemini Live session runner (PCM in/out + tools)."""

from __future__ import annotations

import asyncio
import base64
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from django.conf import settings

from apps.common.envutil import gemini_voice_api_key, voice_live_enabled
from apps.voice.live_tools import (
    LIVE_TOOL_DECLARATIONS,
    SERAH_LIVE_SYSTEM,
    execute_live_tool,
)
from apps.voice.tts import _gemini_voice, resolve_persona

logger = logging.getLogger(__name__)

EmitFn = Callable[[dict[str, Any]], Awaitable[None]]


class LiveSessionRunner:
    """Owns one Gemini Live connection for an authenticated Care Plus user."""

    def __init__(
        self,
        *,
        user,
        emit: EmitFn,
        ui_language: str | None = "English",
        voice_persona: str | None = "female",
    ) -> None:
        self.user = user
        self.emit = emit
        self.ui_language = ui_language if ui_language in ("English", "Tamil", "Sinhala") else "English"
        self.voice_persona = resolve_persona(voice_persona)
        self._session = None
        self._task: asyncio.Task | None = None
        self._closed = False
        self._has_prior_match = False
        self._prior_intent: dict | None = None
        self._prior_match: dict | None = None
        self._audio_q: asyncio.Queue[bytes | None] = asyncio.Queue()

    @property
    def model(self) -> str:
        return (
            getattr(settings, "VOICE_LIVE_MODEL", "") or "gemini-3.1-flash-live-preview"
        ).strip()

    async def start(self) -> None:
        if not voice_live_enabled():
            await self.emit(
                {
                    "type": "live.unavailable",
                    "reason": "Live disabled or GEMINI_VOICE_API_KEY / GEMINI_API_KEY missing",
                }
            )
            return
        api_key = gemini_voice_api_key()
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            await self.emit(
                {"type": "live.unavailable", "reason": "google-genai package not installed"}
            )
            return

        client = genai.Client(api_key=api_key)
        voice_name = _gemini_voice(self.voice_persona)
        lang_line = f"Preferred language: {self.ui_language}."
        config = {
            "response_modalities": ["AUDIO"],
            "system_instruction": f"{SERAH_LIVE_SYSTEM}\n{lang_line}",
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {"voice_name": voice_name},
                }
            },
            "input_audio_transcription": {},
            "output_audio_transcription": {},
            "tools": [{"function_declarations": LIVE_TOOL_DECLARATIONS}],
        }

        try:
            self._session = await client.aio.live.connect(
                model=self.model, config=config
            ).__aenter__()
        except Exception as exc:
            logger.exception("Gemini Live connect failed")
            await self.emit({"type": "live.unavailable", "reason": str(exc)[:240]})
            return

        await self.emit(
            {
                "type": "live.ready",
                "model": self.model,
                "voice": voice_name,
                "ui_language": self.ui_language,
            }
        )
        self._task = asyncio.create_task(self._pump(types))

    async def push_pcm(self, pcm: bytes) -> None:
        if self._closed or not pcm:
            return
        await self._audio_q.put(pcm)

    async def push_text(self, text: str) -> None:
        if self._closed or not self._session or not text.strip():
            return
        try:
            await self._session.send_client_content(
                turns={"role": "user", "parts": [{"text": text.strip()}]},
                turn_complete=True,
            )
        except Exception:
            logger.exception("Live send text failed")

    async def interrupt(self) -> None:
        # Best-effort: empty queue so barge-in feels snappy; model barge-in is native.
        while not self._audio_q.empty():
            try:
                self._audio_q.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def close(self) -> None:
        self._closed = True
        await self._audio_q.put(None)
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        if self._session is not None:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                logger.exception("Live session close failed")
            self._session = None

    async def _pump(self, types) -> None:
        assert self._session is not None
        sender = asyncio.create_task(self._send_loop())
        try:
            async for response in self._session.receive():
                if self._closed:
                    break
                await self._handle_response(response, types)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Live receive loop failed")
            await self.emit({"type": "live.error", "message": str(exc)[:240]})
        finally:
            sender.cancel()
            try:
                await sender
            except (asyncio.CancelledError, Exception):
                pass
            await self.emit({"type": "live.closed"})

    async def _send_loop(self) -> None:
        assert self._session is not None
        while not self._closed:
            chunk = await self._audio_q.get()
            if chunk is None:
                break
            try:
                await self._session.send_realtime_input(
                    audio={"data": chunk, "mime_type": "audio/pcm;rate=16000"}
                )
            except Exception:
                logger.exception("Live send audio failed")
                break

    async def _handle_response(self, response, types) -> None:
        # PCM audio chunks
        data = getattr(response, "data", None)
        if data:
            raw = data if isinstance(data, (bytes, bytearray)) else bytes(data)
            await self.emit(
                {
                    "type": "live.audio",
                    "data": base64.b64encode(raw).decode("ascii"),
                    "mime": "audio/pcm;rate=24000",
                }
            )

        sc = getattr(response, "server_content", None)
        if sc is not None:
            in_t = getattr(sc, "input_transcription", None)
            if in_t and getattr(in_t, "text", None):
                await self.emit(
                    {
                        "type": "live.input_transcript",
                        "text": in_t.text,
                        "final": bool(getattr(in_t, "finished", False)),
                    }
                )
            out_t = getattr(sc, "output_transcription", None)
            if out_t and getattr(out_t, "text", None):
                await self.emit(
                    {
                        "type": "live.output_transcript",
                        "text": out_t.text,
                        "final": bool(getattr(out_t, "finished", False)),
                    }
                )

        tool_call = getattr(response, "tool_call", None)
        if tool_call and getattr(tool_call, "function_calls", None):
            await self._handle_tools(tool_call.function_calls, types)

    async def _handle_tools(self, function_calls, types) -> None:
        assert self._session is not None
        responses = []
        for fc in function_calls:
            name = getattr(fc, "name", "") or ""
            args = dict(getattr(fc, "args", None) or {})
            await self.emit({"type": "live.tool", "name": name, "status": "running"})
            result = await execute_live_tool(
                user=self.user,
                name=name,
                args=args,
                ui_language=self.ui_language,
                voice_persona=self.voice_persona,
                has_prior_match=self._has_prior_match,
                prior_intent=self._prior_intent,
                prior_match=self._prior_match,
            )
            if result.get("intent"):
                self._prior_intent = result["intent"]
            if result.get("match"):
                self._has_prior_match = True
                self._prior_match = result["match"]
                await self.emit({"type": "live.match", "payload": result["match"]})
            if result.get("clear_match") or result.get("cleared"):
                self._has_prior_match = False
                self._prior_match = None
                await self.emit({"type": "live.match", "payload": None, "cleared": True})
            if result.get("reply"):
                await self.emit(
                    {
                        "type": "live.output_transcript",
                        "text": result["reply"],
                        "final": True,
                        "from_tool": True,
                    }
                )
            await self.emit(
                {
                    "type": "live.tool",
                    "name": name,
                    "status": "done",
                    "route": result.get("route"),
                }
            )
            responses.append(
                types.FunctionResponse(
                    id=getattr(fc, "id", None),
                    name=name,
                    response=result,
                )
            )
        if responses:
            await self._session.send_tool_response(function_responses=responses)
