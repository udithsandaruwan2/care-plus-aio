"""Health metric ingest and windowed aggregates (Step 45)."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Avg, Count, Max, Min
from django.db.models.functions import TruncMinute
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import Role
from apps.matching.models import CareRelationship, CareRelationshipStatus

from .models import HealthMetric


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
    return HealthMetric.objects.create(
        patient=patient,
        kind=kind,
        value=float(value),
        unit=(unit or "").strip(),
        source=(source or "manual").strip()[:64],
        recorded_at=recorded_at or timezone.now(),
        metadata=metadata or {},
    )


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

