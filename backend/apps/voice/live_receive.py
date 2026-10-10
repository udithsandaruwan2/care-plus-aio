"""Keep a Gemini Live receive loop open across turns.

google-genai 1.14 ``AsyncSession.receive()`` yields one model turn and
returns when ``turn_complete`` is set. A single ``async for`` over that
iterator ends the conversation after her first reply, including the turn a
barge just cut off, so the next answer never arrives.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any


async def iter_session_messages(
    session: Any,
    closed: Callable[[], bool],
) -> AsyncIterator[Any]:
    """Yield every server message until ``closed`` is true."""
    while not closed():
        async for response in session.receive():
            yield response
            if closed():
                return
