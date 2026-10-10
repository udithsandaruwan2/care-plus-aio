"""The Live receive loop must outlast one turn_complete."""

from __future__ import annotations

import unittest

from apps.voice.live_receive import iter_session_messages


class _TurnSession:
    """Mimic google-genai 1.14: each receive() ends when the turn ends."""

    def __init__(self, turns: list[list[str]]) -> None:
        self._turns = list(turns)
        self.calls = 0

    def receive(self):
        self.calls += 1
        items = self._turns.pop(0) if self._turns else []

        async def _gen():
            for item in items:
                yield item

        return _gen()


class LiveReceiveTests(unittest.TestCase):
    def test_barge_turn_still_receives_the_next_reply(self) -> None:
        session = _TurnSession(
            [
                ["greeting-audio", "turn-complete"],
                ["answer-audio", "turn-complete"],
            ]
        )
        closed = False

        async def collect():
            out = []
            async for message in iter_session_messages(session, lambda: closed):
                out.append(message)
                if message == "answer-audio":
                    return out
            return out

        import asyncio

        heard = asyncio.run(collect())
        self.assertEqual(heard, ["greeting-audio", "turn-complete", "answer-audio"])
        self.assertEqual(session.calls, 2)

    def test_close_stops_the_next_receive(self) -> None:
        session = _TurnSession([["turn-complete"], ["should-not-hear"]])
        flags = {"closed": False}

        async def collect():
            out = []
            async for message in iter_session_messages(session, lambda: flags["closed"]):
                out.append(message)
                flags["closed"] = True
            return out

        import asyncio

        heard = asyncio.run(collect())
        self.assertEqual(heard, ["turn-complete"])
        self.assertEqual(session.calls, 1)


if __name__ == "__main__":
    unittest.main()
