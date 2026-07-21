"""Medical record create / attachment upload services (Step 35)."""

from __future__ import annotations

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import Role
from apps.vocab.models import ConditionTerm

from .attachments import validate_upload_file
from .models import MedicalRecord, MedicalRecordAttachment


def records_queryset_for_user(user):
    qs = MedicalRecord.objects.select_related("condition", "patient").prefetch_related(
        "attachments"
    )
    role = getattr(user, "role", None)
    if role in (Role.ADMIN, Role.AUDITOR):
        patient_id = None  # optional filter applied in view
        return qs
    if role == Role.PATIENT:
        return qs.filter(patient=user)
    if role == Role.CAREGIVER:
        from apps.matching.models import CareRelationship, CareRelationshipStatus

        patient_ids = CareRelationship.objects.filter(
            caregiver__user_id=user.pk,
            status=CareRelationshipStatus.ACTIVE,
        ).values_list("patient_id", flat=True)
        return qs.filter(patient_id__in=patient_ids)
    return qs.none()


def can_write_medical_record(user, record: MedicalRecord) -> bool:
    return getattr(user, "role", None) == Role.PATIENT and user.pk == record.patient_id


@transaction.atomic
def create_medical_record(
    *,
    patient,
    condition_slug: str,
    title: str,
    description: str = "",
    sensitive_notes: str = "",
    recorded_at=None,
    upload_file=None,
) -> MedicalRecord:
    if getattr(patient, "role", None) != Role.PATIENT:
        raise PermissionDenied("Only patients can create medical records.")

    try:
        condition = ConditionTerm.objects.get(slug=condition_slug, active=True)
    except ConditionTerm.DoesNotExist as exc:
        raise ValidationError("Active condition not found.") from exc

    record = MedicalRecord.objects.create(
        patient=patient,
        condition=condition,
        title=(title or "").strip(),
        description=(description or "").strip(),
        recorded_at=recorded_at,
    )
    if sensitive_notes:
        record.sensitive_notes = sensitive_notes
        record.save(update_fields=["sensitive_notes_ciphertext", "updated_at"])

    if upload_file is not None:
        upload_attachment(record=record, patient=patient, uploaded_file=upload_file)

    return record


@transaction.atomic
def upload_attachment(*, record: MedicalRecord, patient, uploaded_file) -> MedicalRecordAttachment:
    if not can_write_medical_record(patient, record):
        raise PermissionDenied("You cannot upload attachments for this record.")

    content_type = validate_upload_file(uploaded_file)
    original_name = getattr(uploaded_file, "name", "") or "upload"
    size = getattr(uploaded_file, "size", 0) or 0

    attachment = MedicalRecordAttachment.objects.create(
        record=record,
        original_name=original_name[:255],
        content_type=content_type,
        size_bytes=size,
    )
    attachment.file.save(original_name, uploaded_file, save=True)
    if attachment.size_bytes <= 0 and attachment.file:
        attachment.size_bytes = attachment.file.size
        attachment.save(update_fields=["size_bytes"])
    return attachment
