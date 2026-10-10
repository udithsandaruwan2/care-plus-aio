"""Forward the user's microphone to Gemini Live.

While she is speaking the client sends nothing, so her own voice is not
fed back. An idle timer used to close that pause a second into her reply,
which cuts the line off. The client now asks for ``audio_stream_end`` only
when she takes the mic, and only after the stream carried real audio.
Silence is forwarded but does not close the line.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any


class _EndAudio:
    """Commit cached user audio. Not a microphone chunk."""


END_AUDIO = _EndAudio()


def pcm_has_energy(chunk: bytes) -> bool:
    """True when 16-bit PCM is not the silence the gate sends for a quiet room."""
    limit = len(chunk) - (len(chunk) % 2)
    for offset in range(0, limit, 2):
        sample = int.from_bytes(chunk[offset : offset + 2], "little", signed=True)
        if sample != 0:
            return True
    return False


async def pump_mic_audio(
    session: Any,
    queue: asyncio.Queue,
    closed: Callable[[], bool],
) -> None:
    """Send queued PCM. Flush only after real user audio, when she takes the mic."""
    stream_open = False
    heard_user = False
    while not closed():
        chunk = await queue.get()
        if chunk is None:
            return
        if chunk is END_AUDIO:
            # Silence alone must not close the stream. That end signal arrives
            # as she starts talking and cuts the reply off.
            if stream_open and heard_user:
                await session.send_realtime_input(audio_stream_end=True)
            stream_open = False
            heard_user = False
            continue
        if pcm_has_energy(chunk):
            heard_user = True
        await session.send_realtime_input(
            audio={"data": chunk, "mime_type": "audio/pcm;rate=16000"}
        )
        stream_open = True
