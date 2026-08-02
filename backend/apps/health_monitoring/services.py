"""Health metric ingest and windowed aggregates (Step 45)."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Avg, Count, Max, Min
from django.db.models.functions import TruncMinute
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import Role
from apps.matching.models import CareRelationship, CareRelationshipStatus

from .models import HealthEvent, HealthEventType, HealthMetric, HealthMetricKind


def metrics_queryset_for_user(user):
    qs = HealthMetric.objects.select_related("patient")
    role = getattr(user, "role", None)
    if role in (Role.ADMIN, Role.AUDITOR):
        return qs
    if role == Role.PATIENT:
        return qs.filter(patient=user)
    if role == Role.CAREGIVER:
        patient_ids = CareRelationship.objects.filter(
            caregiver__user_id=user.pk,
            status=CareRelationshipStatus.ACTIVE,
        ).values_list("patient_id", flat=True)
        return qs.filter(patient_id__in=patient_ids)
    return qs.none()


def resolve_ingest_patient(*, actor, requested_patient_id: int | None):
    role = getattr(actor, "role", None)
    if role == Role.PATIENT:
        if requested_patient_id and requested_patient_id != actor.pk:
            raise PermissionDenied("Patients can only ingest their own health metrics.")
        return actor
    if role in (Role.ADMIN, Role.AUDITOR):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            return User.objects.get(pk=requested_patient_id)
        except User.DoesNotExist as exc:
            raise ValidationError("Patient not found.") from exc
    raise PermissionDenied("Only patients/admin/auditor can ingest health metrics.")


def ingest_metric(
    *,
    actor,
    patient,
    kind: str,
    value: float,
    unit: str = "",
    source: str = "manual",
    recorded_at=None,
    metadata: dict | None = None,
):
    row = HealthMetric(
        patient=patient,
        kind=kind,
        value=float(value),
        unit=(unit or "").strip(),
        source=(source or "manual").strip()[:64],
        recorded_at=recorded_at or timezone.now(),
    )
    row.metadata = metadata or {}
    row.save()
    return row


def aggregate_window(*, queryset, kind: str, hours: int):
    now = timezone.now()
    start = now - timedelta(hours=hours)
    window_qs = queryset.filter(kind=kind, recorded_at__gte=start)
    stats = window_qs.aggregate(
        count=Count("id"),
        min=Min("value"),
        max=Max("value"),
        avg=Avg("value"),
        latest_ts=Max("recorded_at"),
    )
    latest = window_qs.order_by("-recorded_at").first()
    series = list(
        window_qs.annotate(bucket=TruncMinute("recorded_at"))
        .values("bucket")
        .annotate(avg=Avg("value"), count=Count("id"))
        .order_by("bucket")
    )
    return {
        "kind": kind,
        "window_hours": hours,
        "count": stats["count"] or 0,
        "min": stats["min"],
        "max": stats["max"],
        "avg": stats["avg"],
        "latest": (
            {
                "value": latest.value,
                "unit": latest.unit,
                "source": latest.source,
                "recorded_at": latest.recorded_at,
            }
            if latest
            else None
        ),
        "series": series,
    }


def _emit_health_critical_event(
    *,
    patient_id: int,
    kind: str,
    rule_key: str,
    window_start,
    window_end,
    sample_count: int,
    payload: dict,
    cooldown_minutes: int,
):
    dedupe_after = timezone.now() - timedelta(minutes=max(1, cooldown_minutes))
    exists = HealthEvent.objects.filter(
        patient_id=patient_id,
        event_type=HealthEventType.HEALTH_CRITICAL,
        kind=kind,
        rule_key=rule_key,
        created_at__gte=dedupe_after,
    ).exists()
    if exists:
        return None
    event = HealthEvent(
        patient_id=patient_id,
        event_type=HealthEventType.HEALTH_CRITICAL,
        kind=kind,
        rule_key=rule_key,
        severity="critical",
        window_start=window_start,
        window_end=window_end,
        sample_count=sample_count,
    )
    event.payload = payload
    event.save()
    return event


def detect_glucose_anomalies(
    *,
    now=None,
    lookback_minutes: int = 30,
    min_points: int = 3,
    hypo_threshold: float = 70.0,
    hyper_threshold: float = 180.0,
    cooldown_minutes: int = 30,
):
    """Rules-first detector for hypo/hyperglycemia trend events."""
    now = now or timezone.now()
    start = now - timedelta(minutes=max(1, lookback_minutes))
    rows = (
        HealthMetric.objects.filter(
            kind=HealthMetricKind.BLOOD_GLUCOSE,
            recorded_at__gte=start,
            recorded_at__lte=now,
        )
        .order_by("patient_id", "-recorded_at")
        .values("patient_id", "recorded_at", "value", "unit", "source")
    )

    grouped: dict[int, list[dict]] = {}
    for row in rows:
        bucket = grouped.setdefault(row["patient_id"], [])
        if len(bucket) < min_points:
            bucket.append(row)

    emitted = []
    for patient_id, points in grouped.items():
        if len(points) < min_points:
            continue
        values = [float(p["value"]) for p in points]
        window_start = points[-1]["recorded_at"]
        window_end = points[0]["recorded_at"]
        common_payload = {
            "thresholds": {"hypo": hypo_threshold, "hyper": hyper_threshold},
            "values": values,
            "unit": points[0]["unit"] or "mg/dL",
            "lookback_minutes": lookback_minutes,
        }
        if all(v < hypo_threshold for v in values):
            event = _emit_health_critical_event(
                patient_id=patient_id,
                kind=HealthMetricKind.BLOOD_GLUCOSE,
                rule_key="hypoglycemia_trend",
                window_start=window_start,
                window_end=window_end,
                sample_count=len(values),
                payload=common_payload,
                cooldown_minutes=cooldown_minutes,
            )
            if event:
                emitted.append(event)
        if all(v > hyper_threshold for v in values):
            event = _emit_health_critical_event(
                patient_id=patient_id,
                kind=HealthMetricKind.BLOOD_GLUCOSE,
                rule_key="hyperglycemia_trend",
                window_start=window_start,
                window_end=window_end,
                sample_count=len(values),
                payload=common_payload,
                cooldown_minutes=cooldown_minutes,
            )
            if event:
                emitted.append(event)
    return emitted

