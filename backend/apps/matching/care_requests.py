"""CareRequest create/cancel helpers (Step 23)."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role

from .models import (
    ACTIVE_CARE_REQUEST_STATUSES,
    CaregiverProfile,
    CareRequest,
    CareRequestStatus,
    MatchRun,
)
from .patient_guards import ensure_patient_can_request_care


def care_request_ttl() -> timedelta:
    hours = int(getattr(settings, "CARE_REQUEST_TTL_HOURS", 72))
    return timedelta(hours=max(1, hours))


def has_active_care_request(patient_id: int, caregiver_id: int) -> bool:
    return CareRequest.objects.filter(
        patient_id=patient_id,
        caregiver_id=caregiver_id,
        status__in=ACTIVE_CARE_REQUEST_STATUSES,
    ).exists()


@transaction.atomic
def create_care_request(
    *,
    patient,
    caregiver: CaregiverProfile,
    message: str = "",
    match_run: MatchRun | None = None,
    match_snapshot: dict | None = None,
) -> CareRequest:
    if getattr(patient, "role", None) != Role.PATIENT:
        raise ValidationError("Only patients can create care requests.")
    ensure_patient_can_request_care(patient)

    if not caregiver.is_active:
        raise ValidationError("This caregiver is not available for hire.")
    if not caregiver.is_available:
        raise ValidationError("This caregiver is currently unavailable.")

    if has_active_care_request(patient.pk, caregiver.pk):
        raise ValidationError(
            "An active care request already exists for this caregiver.",
            code="duplicate_active_request",
        )

    if match_run is not None and match_run.user_id not in (None, patient.pk):
        raise ValidationError("match_run does not belong to this patient.")

    now = timezone.now()
    return CareRequest.objects.create(
        patient=patient,
        caregiver=caregiver,
        status=CareRequestStatus.PENDING,
        message=(message or "").strip(),
        match_run=match_run,
        match_snapshot=match_snapshot or {},
        expires_at=now + care_request_ttl(),
    )


def cancel_care_request(request: CareRequest, *, patient) -> CareRequest:
    if request.patient_id != patient.pk:
        raise ValidationError("You can only cancel your own care requests.")
    if request.status != CareRequestStatus.PENDING:
        raise ValidationError(f"Cannot cancel a request in status '{request.status}'.")
    request.status = CareRequestStatus.CANCELLED
    request.responded_at = timezone.now()
    request.save(update_fields=["status", "responded_at", "updated_at"])
    return request


def expire_stale_care_requests() -> int:
    """Mark pending requests past expires_at as expired."""
    now = timezone.now()
    updated = CareRequest.objects.filter(
        status=CareRequestStatus.PENDING,
        expires_at__lt=now,
    ).update(status=CareRequestStatus.EXPIRED, responded_at=now, updated_at=now)
    return updated
