"""Medical record read access + audit (Step 34)."""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied

from apps.accounts.audit import record_audit
from apps.accounts.models import AuditAction, Role
from apps.matching.models import CareRelationship, CareRelationshipStatus

from .models import MedicalRecord


def can_read_medical_record(user, record: MedicalRecord) -> bool:
    role = getattr(user, "role", None)
    if role in (Role.ADMIN, Role.AUDITOR):
        return True
    if user.pk == record.patient_id:
        return True
    if role == Role.CAREGIVER:
        return CareRelationship.objects.filter(
            patient_id=record.patient_id,
            caregiver__user_id=user.pk,
            status=CareRelationshipStatus.ACTIVE,
        ).exists()
    return False


def read_medical_record(*, user, record: MedicalRecord, request=None) -> MedicalRecord:
    """Authorize read, audit VIEW_HEALTH, return record (decrypt via sensitive_notes)."""
    if not can_read_medical_record(user, record):
        raise PermissionDenied("You cannot access this medical record.")

    record_audit(
        actor=user,
        action=AuditAction.VIEW_HEALTH,
        request=request,
        target_type="medical_record",
        target_id=record.pk,
        metadata={
            "patient_id": record.patient_id,
            "condition_slug": record.condition.slug if record.condition_id else "",
            "source": "medical_record_read",
        },
        async_=False,
    )
    # Touch decrypted field so callers/tests verify roundtrip.
    _ = record.sensitive_notes
    return record
