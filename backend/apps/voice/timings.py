"""Per-stage voice-turn clocks (Step 77)."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

from apps.common.observability import request_id_var

logger = logging.getLogger("apps.voice.timings")

STAGE_KEYS = ("asr_ms", "intent_ms", "route_ms", "match_ms", "chat_ms", "tts_ms")


def empty_timings(*, request_id: str = "") -> dict:
    return {
        "asr_ms": 0,
        "intent_ms": 0,
        "route_ms": 0,
        "match_ms": 0,
        "chat_ms": 0,
        "tts_ms": 0,
        "total_ms": 0,
        "request_id": request_id,
    }


class StageClock:
    """Wall clock for a voice turn plus named stage spans that may nest sequentially."""

    def __init__(self) -> None:
        self._wall0 = time.perf_counter()
        self.stages = empty_timings(request_id=request_id_var.get() or "")

    @contextmanager
    def span(self, key: str) -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.stages[key] = int(self.stages.get(key, 0)) + int(
                (time.perf_counter() - t0) * 1000
            )

    def finish(self) -> dict:
        self.stages["total_ms"] = int((time.perf_counter() - self._wall0) * 1000)
        self.stages["request_id"] = self.stages.get("request_id") or request_id_var.get() or ""
        return dict(self.stages)


def stage_sum(timings: dict) -> int:
    return sum(int(timings.get(k, 0) or 0) for k in STAGE_KEYS)


def log_turn_timings(timings: dict, *, route: str, situation: str) -> None:
    extra = {k: int(timings.get(k, 0) or 0) for k in (*STAGE_KEYS, "total_ms")}
    extra["route"] = route
    extra["situation"] = situation
    rid = timings.get("request_id") or request_id_var.get() or ""
    if rid:
        extra["request_id"] = rid
    logger.info("voice.turn.timings", extra=extra)


def persist_turn_timings(
    user,
    timings: dict,
    *,
    route: str,
    situation: str,
) -> None:
    from .models import VoiceTurnTiming

    VoiceTurnTiming.objects.create(
        user=user,
        request_id=str(timings.get("request_id") or request_id_var.get() or ""),
        route=route or "",
        situation=situation or "",
        asr_ms=int(timings.get("asr_ms") or 0),
        intent_ms=int(timings.get("intent_ms") or 0),
        route_ms=int(timings.get("route_ms") or 0),
        match_ms=int(timings.get("match_ms") or 0),
        chat_ms=int(timings.get("chat_ms") or 0),
        tts_ms=int(timings.get("tts_ms") or 0),
        total_ms=int(timings.get("total_ms") or 0),
    )


def finalize_turn(
    user,
    payload: dict,
    timings: dict,
    *,
    route: str,
    situation: str,
) -> dict:
    payload["timings"] = timings
    log_turn_timings(timings, route=route, situation=situation)
    try:
        persist_turn_timings(user, timings, route=route, situation=situation)
    except Exception:  # noqa: BLE001 — never fail a turn on metrics
        logger.debug("voice turn timing persist failed", exc_info=True)
    return payload
