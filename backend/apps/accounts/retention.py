"""Scheduled retention / anonymization for active accounts (Step 106).

Erasure (Step 69) remains immediate. This module applies TTLs to data that
would otherwise accumulate forever on live accounts:

- VoiceIntent: scrub encrypted transcript/condition past TTL
- Inactive DialogueSession: wipe turns / route_history / chips past TTL
- HealthMetric: downsample raw samples older than TTL to one daily mean
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Avg
from django.utils import timezone


def retention_voice_intent_days() -> int:
    return max(1, int(getattr(settings, "RETENTION_VOICE_INTENT_DAYS", 90)))


def retention_dialogue_session_days() -> int:
    return max(1, int(getattr(settings, "RETENTION_DIALOGUE_SESSION_DAYS", 30)))


def retention_health_metric_raw_days() -> int:
    return max(1, int(getattr(settings, "RETENTION_HEALTH_METRIC_RAW_DAYS", 90)))


DOWNSAMPLED_SOURCE = "downsampled"


def _cutoff(days: int):
    return timezone.now() - timedelta(days=days)


def anonymize_stale_voice_intents(*, days: int | None = None) -> int:
    """Blank PHI text on VoiceIntent rows older than the TTL. Idempotent."""
    from apps.voice.models import VoiceIntent

    cutoff = _cutoff(retention_voice_intent_days() if days is None else days)
    n = 0
    for intent in VoiceIntent.objects.filter(ts__lt=cutoff).iterator(chunk_size=200):
        if not intent.raw_text and not intent.condition:
            continue
        intent.raw_text = ""
        intent.condition = ""
        intent.save(update_fields=["raw_text_ciphertext", "condition_ciphertext"])
        n += 1
    return n


def scrub_stale_dialogue_sessions(*, days: int | None = None) -> int:
    """Wipe memory on inactive sessions past TTL. Idempotent."""
    from apps.voice.models import DialogueSession

    cutoff = _cutoff(retention_dialogue_session_days() if days is None else days)
    n = 0
    for session in DialogueSession.objects.filter(active=False, updated_at__lt=cutoff).iterator(
        chunk_size=100
    ):
        dirty = bool(session.turns) or bool(session.route_history) or bool(session.intent_chips)
        if not dirty and not session.open_questions:
            continue
        session.turns = []
        session.route_history = []
        session.intent_chips = {}
        session.open_questions = []
        session.last_match_run = None
        session.save(
            update_fields=[
                "turns_ciphertext",
                "route_history",
                "intent_chips_ciphertext",
                "open_questions",
                "last_match_run",
                "updated_at",
            ]
        )
        n += 1
    return n


def downsample_stale_health_metrics(*, days: int | None = None) -> dict[str, int]:
    """Replace old raw HealthMetric rows with one daily mean per patient/kind.

    Idempotent: skips days that already have a ``source=downsampled`` row and
    only deletes non-downsampled samples past the cutoff.
    """
    from apps.health_monitoring.models import HealthMetric

    cutoff = _cutoff(retention_health_metric_raw_days() if days is None else days)
    raw = HealthMetric.objects.filter(recorded_at__lt=cutoff).exclude(source=DOWNSAMPLED_SOURCE)
    if not raw.exists():
        return {"groups": 0, "deleted": 0, "created": 0}

    # Collect (patient_id, kind, date) buckets that still have raw rows.
    buckets: dict[tuple[int, str, date], list[int]] = defaultdict(list)
    units: dict[tuple[int, str, date], str] = {}
    for row in raw.iterator(chunk_size=500):
        day = timezone.localtime(row.recorded_at).date()
        key = (row.patient_id, row.kind, day)
        buckets[key].append(row.pk)
        if key not in units:
            units[key] = row.unit or ""

    created = 0
    deleted = 0
    for (patient_id, kind, day), ids in buckets.items():
        noon = timezone.make_aware(datetime.combine(day, time(12, 0)), timezone.get_current_timezone())
        already = HealthMetric.objects.filter(
            patient_id=patient_id,
            kind=kind,
            source=DOWNSAMPLED_SOURCE,
            recorded_at__date=day,
        ).exists()
        with transaction.atomic():
            if not already:
                avg = (
                    HealthMetric.objects.filter(pk__in=ids).aggregate(v=Avg("value"))["v"]
                )
                if avg is None:
                    continue
                HealthMetric.objects.create(
                    patient_id=patient_id,
                    kind=kind,
                    value=float(avg),
                    unit=units.get((patient_id, kind, day), ""),
                    source=DOWNSAMPLED_SOURCE,
                    recorded_at=noon,
                )
                created += 1
            deleted += HealthMetric.objects.filter(pk__in=ids).delete()[0]

    return {"groups": len(buckets), "deleted": deleted, "created": created}


def apply_retention_policy() -> dict[str, Any]:
    """Run all retention passes. Safe to call repeatedly (idempotent)."""
    voice_n = anonymize_stale_voice_intents()
    session_n = scrub_stale_dialogue_sessions()
    health = downsample_stale_health_metrics()
    return {
        "voice_intents_anonymized": voice_n,
        "dialogue_sessions_scrubbed": session_n,
        "health_metrics": health,
        "ttls": {
            "voice_intent_days": retention_voice_intent_days(),
            "dialogue_session_days": retention_dialogue_session_days(),
            "health_metric_raw_days": retention_health_metric_raw_days(),
        },
    }
