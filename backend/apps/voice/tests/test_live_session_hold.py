"""The Live socket stays open for the whole conversation."""

from __future__ import annotations

import unittest

from apps.voice.live_bridge import LiveSessionRunner
from apps.voice.live_tools import live_reply_language


class _Connect:
    def __init__(self) -> None:
        self.exited = False

    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self.exited = True
        return False


class LiveSessionHoldTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_releases_the_connect_manager(self) -> None:
        async def emit(_payload):
            return None

        runner = LiveSessionRunner(user=object(), emit=emit)
        connect = _Connect()
        runner._live_cm = connect
        runner._session = object()
        await runner.close()
        self.assertTrue(connect.exited)
        self.assertIsNone(runner._live_cm)
        self.assertIsNone(runner._session)

    def test_reply_covers_english_tamil_and_sinhala(self) -> None:
        line = live_reply_language("Tamil")
        self.assertIn("Tamil", line)
        self.assertIn("English", line)
        self.assertIn("Sinhala", line)
        self.assertIn("unclear: Tamil", line)
        self.assertIn("Tamil sounds", line)
        self.assertIn("English sounds", line)
        self.assertIn("Sinhala sounds", line)
