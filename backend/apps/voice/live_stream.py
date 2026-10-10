"""Forward the user's microphone to Gemini Live.

While she is speaking the client sends nothing, so her own voice is not
fed back. A pause longer than a second leaves the user's last words cached
unless the stream is closed. Gemini documents that close as
``audio_stream_end``. The next real chunk opens the stream again.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

# Live API: a mic pause longer than this must be flushed.
MIC_STREAM_PAUSE_SEC = 1.0


async def pump_mic_audio(
    session: Any,
    queue: asyncio.Queue,
    closed: Callable[[], bool],
    pause_sec: float = MIC_STREAM_PAUSE_SEC,
) -> None:
    """Send queued PCM. Flush once when the queue stays empty past ``pause_sec``."""
    stream_open = False
    while not closed():
        try:
            chunk = await asyncio.wait_for(queue.get(), timeout=pause_sec)
        except asyncio.TimeoutError:
            if not stream_open:
                continue
            stream_open = False
            await session.send_realtime_input(audio_stream_end=True)
            continue
        if chunk is None:
            return
        await session.send_realtime_input(
            audio={"data": chunk, "mime_type": "audio/pcm;rate=16000"}
        )
        stream_open = True
