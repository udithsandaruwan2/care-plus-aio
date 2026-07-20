"""CareRequest create/cancel/respond helpers (Steps 23–24)."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role

from .interactions import log_interaction
from .models import (
    ACTIVE_CARE_REQUEST_STATUSES,
    CaregiverProfile,
    CareRelationship,
    CareRelationshipStatus,
    CareRequest,
    CareRequestStatus,
    InteractionKind,
    MatchRun,
)
from .patient_guards import ensure_patient_can_request_care
from .push import push_care_request_update


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
    care_request = CareRequest.objects.create(
        patient=patient,
        caregiver=caregiver,
        status=CareRequestStatus.PENDING,
        message=(message or "").strip(),
        match_run=match_run,
        match_snapshot=match_snapshot or {},
        expires_at=now + care_request_ttl(),
    )
    log_interaction(
        patient,
        caregiver,
        InteractionKind.REQUEST,
        metadata={"care_request_id": care_request.pk},
    )
    push_care_request_update(
        caregiver.user_id,
        _care_request_payload(care_request, event="created"),
    )
    return care_request


def cancel_care_request(request: CareRequest, *, patient) -> CareRequest:
    if request.patient_id != patient.pk:
        raise ValidationError("You can only cancel your own care requests.")
    if request.status != CareRequestStatus.PENDING:
        raise ValidationError(f"Cannot cancel a request in status '{request.status}'.")
    request.status = CareRequestStatus.CANCELLED
    request.responded_at = timezone.now()
    request.save(update_fields=["status", "responded_at", "updated_at"])
    push_care_request_update(
        request.caregiver.user_id,
        _care_request_payload(request, event="cancelled"),
    )
    return request


def _care_request_payload(request: CareRequest, *, event: str) -> dict:
    return {
        "event": event,
        "id": request.pk,
        "status": request.status,
        "patient_id": request.patient_id,
        "caregiver_id": request.caregiver_id,
        "caregiver_name": request.caregiver.display_name,
        "patient_email": request.patient.email,
        "message": request.message,
        "responded_at": request.responded_at.isoformat() if request.responded_at else None,
    }


@transaction.atomic
def accept_care_request(request: CareRequest, *, caregiver_user) -> tuple[CareRequest, CareRelationship]:
    if getattr(caregiver_user, "role", None) != Role.CAREGIVER:
        raise ValidationError("Only caregivers can accept care requests.")
    if request.caregiver.user_id != caregiver_user.pk:
        raise ValidationError("This request is not in your inbox.")
    if request.status != CareRequestStatus.PENDING:
        raise ValidationError(f"Cannot accept a request in status '{request.status}'.")

    now = timezone.now()
    request.status = CareRequestStatus.ACCEPTED
    request.responded_at = now
    request.save(update_fields=["status", "responded_at", "updated_at"])

    relationship = CareRelationship.objects.create(
        patient=request.patient,
        caregiver=request.caregiver,
        care_request=request,
        status=CareRelationshipStatus.PENDING_PAYMENT,
    )

    log_interaction(
        request.patient,
        request.caregiver,
        InteractionKind.ACCEPT,
        metadata={"care_request_id": request.pk, "relationship_id": relationship.pk},
    )

    payload = _care_request_payload(request, event="accepted")
    payload["relationship_id"] = relationship.pk
    payload["relationship_status"] = relationship.status
    push_care_request_update(request.patient_id, payload)
    return request, relationship


@transaction.atomic
def reject_care_request(
    request: CareRequest,
    *,
    caregiver_user,
    reason: str = "",
) -> CareRequest:
    if getattr(caregiver_user, "role", None) != Role.CAREGIVER:
        raise ValidationError("Only caregivers can reject care requests.")
    if request.caregiver.user_id != caregiver_user.pk:
        raise ValidationError("This request is not in your inbox.")
    if request.status != CareRequestStatus.PENDING:
        raise ValidationError(f"Cannot reject a request in status '{request.status}'.")

    request.status = CareRequestStatus.REJECTED
    request.responded_at = timezone.now()
    if reason.strip():
        request.message = f"{request.message}\n\n[Rejection note] {reason.strip()}".strip()
    request.save(update_fields=["status", "responded_at", "message", "updated_at"])

    payload = _care_request_payload(request, event="rejected")
    if reason.strip():
        payload["reason"] = reason.strip()
    push_care_request_update(request.patient_id, payload)
    return request


def expire_stale_care_requests() -> int:
    """Mark pending requests past expires_at as expired (with email/WS notice)."""
    from .care_request_lifecycle import expire_stale_care_requests_with_notice

    return expire_stale_care_requests_with_notice()
