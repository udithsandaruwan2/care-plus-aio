"""CareRelationship lifecycle — activate, end, availability sync (Step 25)."""

from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role

from .models import CareRelationship, CareRelationshipStatus, CaregiverProfile


def _participant(rel: CareRelationship, user) -> bool:
    if user.pk == rel.patient_id:
        return True
    return getattr(user, "role", None) == Role.CAREGIVER and rel.caregiver.user_id == user.pk


def patient_has_active_primary(patient_id: int, *, exclude_id: int | None = None) -> bool:
    qs = CareRelationship.objects.filter(
        patient_id=patient_id,
        status=CareRelationshipStatus.ACTIVE,
        is_primary=True,
    )
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


def sync_caregiver_availability(caregiver: CaregiverProfile) -> CaregiverProfile:
    """Mark unavailable while an active care link exists; otherwise free for matching."""
    has_active = CareRelationship.objects.filter(
        caregiver_id=caregiver.pk,
        status=CareRelationshipStatus.ACTIVE,
    ).exists()
    desired = not has_active
    if caregiver.is_available != desired:
        caregiver.is_available = desired
        caregiver.save(update_fields=["is_available", "updated_at"])
    return caregiver


def relationship_payload(rel: CareRelationship, *, event: str) -> dict:
    return {
        "event": event,
        "id": rel.pk,
        "status": rel.status,
        "is_primary": rel.is_primary,
        "patient_id": rel.patient_id,
        "caregiver_id": rel.caregiver_id,
        "caregiver_name": rel.caregiver.display_name,
        "patient_email": rel.patient.email,
        "started_at": rel.started_at.isoformat() if rel.started_at else None,
        "ended_at": rel.ended_at.isoformat() if rel.ended_at else None,
        "end_reason": rel.end_reason or "",
        "care_request_id": rel.care_request_id,
    }


@transaction.atomic
def activate_relationship(rel: CareRelationship, *, actor) -> CareRelationship:
    if not _participant(rel, actor):
        raise ValidationError("You are not part of this care relationship.")
    if rel.status == CareRelationshipStatus.ENDED:
        raise ValidationError("This care relationship has already ended.")
    if rel.status == CareRelationshipStatus.ACTIVE:
        return rel

    if rel.status != CareRelationshipStatus.PENDING_PAYMENT:
        raise ValidationError(f"Cannot activate a relationship in status '{rel.status}'.")

    if settings.ONE_PRIMARY_CAREGIVER and rel.is_primary:
        if patient_has_active_primary(rel.patient_id, exclude_id=rel.pk):
            raise ValidationError(
                "This patient already has an active primary caregiver.",
                code="primary_caregiver_exists",
            )

    rel.status = CareRelationshipStatus.ACTIVE
    rel.save(update_fields=["status"])
    sync_caregiver_availability(rel.caregiver)
    return rel


@transaction.atomic
def end_relationship(
    rel: CareRelationship,
    *,
    actor,
    reason: str = "",
) -> CareRelationship:
    if not _participant(rel, actor):
        raise ValidationError("You are not part of this care relationship.")
    if rel.status == CareRelationshipStatus.ENDED:
        raise ValidationError("This care relationship has already ended.")

    now = timezone.now()
    rel.status = CareRelationshipStatus.ENDED
    rel.ended_at = now
    if reason.strip():
        rel.end_reason = reason.strip()
    rel.save(update_fields=["status", "ended_at", "end_reason"])
    sync_caregiver_availability(rel.caregiver)
    return rel
