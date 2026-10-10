"""Forward the user's microphone to Gemini Live.

While she is speaking the client sends nothing, so her own voice is not
fed back. An idle timer used to close that pause a second into her reply,
which cuts the line off. The client now asks for ``audio_stream_end`` only
when she takes the mic. The next real chunk opens the stream again.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any


class _EndAudio:
    """Commit cached user audio. Not a microphone chunk."""


END_AUDIO = _EndAudio()


async def pump_mic_audio(
    session: Any,
    queue: asyncio.Queue,
    closed: Callable[[], bool],
) -> None:
    """Send queued PCM. Flush only when the queue carries ``END_AUDIO``."""
    stream_open = False
    while not closed():
        chunk = await queue.get()
        if chunk is None:
            return
        if chunk is END_AUDIO:
            if not stream_open:
                continue
            stream_open = False
            await session.send_realtime_input(audio_stream_end=True)
            continue
        await session.send_realtime_input(
            audio={"data": chunk, "mime_type": "audio/pcm;rate=16000"}
        )
        stream_open = True
