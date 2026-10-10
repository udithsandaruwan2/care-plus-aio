"""A long mic pause must flush cached audio exactly once."""

from __future__ import annotations

import asyncio
import unittest

from apps.voice.live_stream import pump_mic_audio


class _Session:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send_realtime_input(self, **kwargs) -> None:
        self.calls.append(kwargs)


class LiveStreamTests(unittest.TestCase):
    def test_pause_while_she_speaks_flushes_once(self) -> None:
        session = _Session()
        queue: asyncio.Queue = asyncio.Queue()
        flags = {"closed": False}

        async def run() -> None:
            await queue.put(b"care-request")
            task = asyncio.create_task(
                pump_mic_audio(session, queue, lambda: flags["closed"], pause_sec=0.02)
            )
            await asyncio.sleep(0.07)
            flags["closed"] = True
            await queue.put(None)
            await task

        asyncio.run(run())
        kinds = []
        for call in session.calls:
            if "audio" in call:
                kinds.append("audio")
            elif call.get("audio_stream_end"):
                kinds.append("end")
        self.assertEqual(kinds, ["audio", "end"])

    def test_steady_silence_does_not_flush(self) -> None:
        session = _Session()
        queue: asyncio.Queue = asyncio.Queue()

        async def run() -> None:
            for _ in range(4):
                await queue.put(b"\x00\x00")
                await asyncio.sleep(0.01)
            await queue.put(None)
            await pump_mic_audio(session, queue, lambda: False, pause_sec=0.05)

        asyncio.run(run())
        self.assertTrue(all("audio" in call for call in session.calls))
        self.assertFalse(any(call.get("audio_stream_end") for call in session.calls))


if __name__ == "__main__":
    unittest.main()
