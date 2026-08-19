"""Admin analytics aggregations (Step 56)."""

from __future__ import annotations

import math
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count
from django.utils import timezone

from apps.accounts.models import Role
from apps.matching.models import (
    CareRelationship,
    CareRelationshipStatus,
    CareRequest,
    CareRequestStatus,
    MatchRun,
)
from apps.voice.models import VoiceTurnTiming

User = get_user_model()


def _series_from_counts(choices, raw: dict[str, int]) -> list[dict]:
    return [
        {"key": choice.value, "label": str(choice.label), "count": int(raw.get(choice.value, 0))}
        for choice in choices
    ]


def _percentile(sorted_vals: list[int], p: float) -> int | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return int(sorted_vals[0])
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return int(sorted_vals[int(k)])
    lower = sorted_vals[f]
    upper = sorted_vals[c]
    return int(round(lower * (c - k) + upper * (k - f)))


def _latency_stats(vals: list[int], *, window_days: int) -> dict:
    avg = None if not vals else int(round(sum(vals) / len(vals)))
    ordered = sorted(vals)
    return {
        "sample_size": len(vals),
        "p50_ms": _percentile(ordered, 0.50),
        "p95_ms": _percentile(ordered, 0.95),
        "p99_ms": _percentile(ordered, 0.99),
        "avg_ms": avg,
        "window_days": window_days,
    }


def build_admin_analytics(*, window_days: int = 30) -> dict:
    window_days = max(1, min(int(window_days), 365))
    since = timezone.now() - timedelta(days=window_days)

    request_raw = dict(
        CareRequest.objects.values("status").annotate(c=Count("id")).values_list("status", "c")
    )
    role_raw = dict(User.objects.values("role").annotate(c=Count("id")).values_list("role", "c"))
    rel_raw = dict(
        CareRelationship.objects.values("status")
        .annotate(c=Count("id"))
        .values_list("status", "c")
    )

    latency_qs = MatchRun.objects.filter(created_at__gte=since)
    latency_vals = list(latency_qs.order_by("latency_ms").values_list("latency_ms", flat=True))
    avg = latency_qs.aggregate(avg=Avg("latency_ms"))["avg"]

    turn_rows = list(
        VoiceTurnTiming.objects.filter(created_at__gte=since).values(
            "asr_ms",
            "intent_ms",
            "route_ms",
            "match_ms",
            "chat_ms",
            "tts_ms",
            "total_ms",
        )
    )
    turn_stage_stats = {}
    for field in ("asr_ms", "intent_ms", "route_ms", "match_ms", "chat_ms", "tts_ms", "total_ms"):
        stage_vals = [int(row[field]) for row in turn_rows]
        turn_stage_stats[field] = _latency_stats(stage_vals, window_days=window_days)

    return {
        "generated_at": timezone.now().isoformat(),
        "window_days": window_days,
        "requests_by_status": _series_from_counts(CareRequestStatus, request_raw),
        "roles": _series_from_counts(Role, role_raw),
        "match_latency": {
            "sample_size": len(latency_vals),
            "p50_ms": _percentile(latency_vals, 0.50),
            "p95_ms": _percentile(latency_vals, 0.95),
            "p99_ms": _percentile(latency_vals, 0.99),
            "avg_ms": None if avg is None else int(round(float(avg))),
            "window_days": window_days,
        },
        "turn_latency": {
            "sample_size": len(turn_rows),
            "window_days": window_days,
            "p50_ms": turn_stage_stats["total_ms"]["p50_ms"],
            "p95_ms": turn_stage_stats["total_ms"]["p95_ms"],
            "p99_ms": turn_stage_stats["total_ms"]["p99_ms"],
            "avg_ms": turn_stage_stats["total_ms"]["avg_ms"],
            "stages": {k: v for k, v in turn_stage_stats.items() if k != "total_ms"},
        },
        "relationships": {
            "active": int(rel_raw.get(CareRelationshipStatus.ACTIVE, 0)),
            "pending_payment": int(rel_raw.get(CareRelationshipStatus.PENDING_PAYMENT, 0)),
            "ended": int(rel_raw.get(CareRelationshipStatus.ENDED, 0)),
            "by_status": _series_from_counts(CareRelationshipStatus, rel_raw),
        },
    }
