"""Medical record create / update / soft-delete services (Steps 35–37)."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.audit import record_audit
from apps.accounts.models import AuditAction, Role
from apps.vocab.models import ConditionTerm

from .attachments import validate_upload_file
from .models import MedicalRecord, MedicalRecordAttachment


def records_queryset_for_user(user):
    qs = (
        MedicalRecord.objects.filter(deleted_at__isnull=True)
        .select_related("condition", "patient")
        .prefetch_related("attachments")
    )
    role = getattr(user, "role", None)
    if role in (Role.ADMIN, Role.AUDITOR):
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
    return (
        record.deleted_at is None
        and getattr(user, "role", None) == Role.PATIENT
        and user.pk == record.patient_id
    )


def _audit_medical_record(*, actor, action: str, record: MedicalRecord, request=None) -> None:
    record_audit(
        actor=actor,
        action=action,
        request=request,
        target_type="medical_record",
        target_id=record.pk,
        metadata={
            "patient_id": record.patient_id,
            "condition_slug": record.condition.slug if record.condition_id else "",
            "title": record.title,
        },
        async_=False,
    )


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
    request=None,
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

    _audit_medical_record(
        actor=patient,
        action=AuditAction.CREATE_MEDICAL_RECORD,
        record=record,
        request=request,
    )
    return record


@transaction.atomic
def update_medical_record(
    *,
    record: MedicalRecord,
    patient,
    condition_slug: str | None = None,
    title: str | None = None,
    description: str | None = None,
    sensitive_notes: str | None = None,
    recorded_at=...,
    request=None,
) -> MedicalRecord:
    if not can_write_medical_record(patient, record):
        raise PermissionDenied("You cannot update this medical record.")

    update_fields: list[str] = ["updated_at"]

    if condition_slug is not None:
        try:
            condition = ConditionTerm.objects.get(slug=condition_slug, active=True)
        except ConditionTerm.DoesNotExist as exc:
            raise ValidationError("Active condition not found.") from exc
        record.condition = condition
        update_fields.append("condition_id")

    if title is not None:
        record.title = (title or "").strip()
        update_fields.append("title")
    if description is not None:
        record.description = (description or "").strip()
        update_fields.append("description")
    if recorded_at is not ...:
        record.recorded_at = recorded_at
        update_fields.append("recorded_at")
    if sensitive_notes is not None:
        record.sensitive_notes = sensitive_notes
        update_fields.append("sensitive_notes_ciphertext")

    record.save(update_fields=update_fields)
    _audit_medical_record(
        actor=patient,
        action=AuditAction.UPDATE_MEDICAL_RECORD,
        record=record,
        request=request,
    )
    return record


@transaction.atomic
def soft_delete_medical_record(*, record: MedicalRecord, patient, request=None) -> MedicalRecord:
    if not can_write_medical_record(patient, record):
        raise PermissionDenied("You cannot delete this medical record.")

    record.deleted_at = timezone.now()
    record.save(update_fields=["deleted_at", "updated_at"])
    _audit_medical_record(
        actor=patient,
        action=AuditAction.DELETE_MEDICAL_RECORD,
        record=record,
        request=request,
    )
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
