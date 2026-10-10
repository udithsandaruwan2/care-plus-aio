"""Closing the mic stream is explicit, not a timer during her reply."""

from __future__ import annotations

import asyncio
import unittest

from apps.voice.live_stream import END_AUDIO, pump_mic_audio


class _Session:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send_realtime_input(self, **kwargs) -> None:
        self.calls.append(kwargs)


def _kinds(session: _Session) -> list[str]:
    kinds = []
    for call in session.calls:
        if "audio" in call:
            kinds.append("audio")
        elif call.get("audio_stream_end"):
            kinds.append("end")
    return kinds


class LiveStreamTests(unittest.TestCase):
    def test_taking_the_mic_flushes_once_then_the_barge_reopens(self) -> None:
        session = _Session()
        queue: asyncio.Queue = asyncio.Queue()

        async def run() -> None:
            await queue.put(b"care-request")
            await queue.put(END_AUDIO)
            await queue.put(END_AUDIO)
            await queue.put(b"barge")
            await queue.put(None)
            await pump_mic_audio(session, queue, lambda: False)

        asyncio.run(run())
        self.assertEqual(_kinds(session), ["audio", "end", "audio"])

    def test_idle_while_she_speaks_does_not_flush(self) -> None:
        session = _Session()
        queue: asyncio.Queue = asyncio.Queue()

        async def run() -> None:
            await queue.put(b"care-request")
            await queue.put(None)
            await pump_mic_audio(session, queue, lambda: False)

        asyncio.run(run())
        self.assertEqual(_kinds(session), ["audio"])

    def test_silence_then_her_reply_does_not_flush(self) -> None:
        session = _Session()
        queue: asyncio.Queue = asyncio.Queue()

        async def run() -> None:
            await queue.put(b"\x00\x00" * 8)
            await queue.put(END_AUDIO)
            await queue.put(None)
            await pump_mic_audio(session, queue, lambda: False)

        asyncio.run(run())
        self.assertEqual(_kinds(session), ["audio"])


if __name__ == "__main__":
    unittest.main()
