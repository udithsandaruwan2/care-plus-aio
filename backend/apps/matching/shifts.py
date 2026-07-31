"""Shift booking with Redis schedule lock (Step 51)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, ValidationError

from apps.accounts.models import Role
from apps.common.redis_lock import redis_lock
from apps.matching.models import (
    CaregiverAvailabilitySlot,
    CaregiverProfile,
    Shift,
    ShiftStatus,
)
from apps.matching.patient_guards import ensure_patient_can_request_care


class ShiftOverlapConflict(APIException):
    """409 when the requested window is already booked (Step 53 may attach fallback)."""

    status_code = 409
    default_detail = "This time window overlaps an existing booked shift."
    default_code = "shift_overlap"


class ShiftOverlapError(Exception):
    """Raised inside the schedule lock when another booked shift overlaps."""

    def __init__(self, message: str = "This time window overlaps an existing booked shift."):
        self.message = message
        super().__init__(message)


def _as_aware(dt: datetime) -> datetime:
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def shifts_overlap(*, caregiver_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    """True if an active booked shift overlaps [starts_at, ends_at)."""
    return (
        Shift.objects.filter(
            caregiver_id=caregiver_id,
            status=ShiftStatus.BOOKED,
        )
        .filter(starts_at__lt=ends_at, ends_at__gt=starts_at)
        .exists()
    )


def _slot_covers_window(
    *,
    slot: CaregiverAvailabilitySlot,
    starts_at: datetime,
    ends_at: datetime,
) -> bool:
    tz_name = slot.timezone or "Asia/Colombo"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("Asia/Colombo")
    local_start = starts_at.astimezone(tz)
    local_end = ends_at.astimezone(tz)
    if local_start.date() != local_end.date():
        return False
    if local_start.weekday() != slot.weekday:
        return False
    start_t = local_start.timetz().replace(tzinfo=None)
    end_t = local_end.timetz().replace(tzinfo=None)
    return start_t >= slot.start_time and end_t <= slot.end_time


def book_shift(
    *,
    patient,
    caregiver_id: int,
    starts_at: datetime,
    ends_at: datetime,
    notes: str = "",
    availability_slot_id: int | None = None,
    timezone_name: str = "Asia/Colombo",
) -> Shift:
    if getattr(patient, "role", None) != Role.PATIENT:
        raise ValidationError("Only patients can book shifts.")
    ensure_patient_can_request_care(patient)

    starts_at = _as_aware(starts_at)
    ends_at = _as_aware(ends_at)
    if ends_at <= starts_at:
        raise ValidationError("ends_at must be after starts_at.")
    if (ends_at - starts_at).total_seconds() > 24 * 3600:
        raise ValidationError("Shift duration cannot exceed 24 hours.")

    try:
        caregiver = CaregiverProfile.objects.get(pk=caregiver_id)
    except CaregiverProfile.DoesNotExist as exc:
        raise NotFound("Caregiver not found.") from exc

    if not caregiver.is_active or not caregiver.is_available:
        raise ValidationError("This caregiver is not available for booking.")

    slot: CaregiverAvailabilitySlot | None = None
    if availability_slot_id is not None:
        try:
            slot = CaregiverAvailabilitySlot.objects.get(
                pk=availability_slot_id,
                caregiver_id=caregiver.pk,
                is_active=True,
            )
        except CaregiverAvailabilitySlot.DoesNotExist as exc:
            raise ValidationError("availability_slot does not belong to this caregiver.") from exc
        if not _slot_covers_window(slot=slot, starts_at=starts_at, ends_at=ends_at):
            raise ValidationError("Requested window is outside the selected availability slot.")
    else:
        # Soft check: at least one active weekly slot must cover this local window.
        covering = CaregiverAvailabilitySlot.objects.filter(
            caregiver_id=caregiver.pk,
            is_active=True,
        )
        if covering.exists():
            if not any(
                _slot_covers_window(slot=s, starts_at=starts_at, ends_at=ends_at) for s in covering
            ):
                raise ValidationError(
                    "Requested window does not fall in any published availability slot.",
                    code="outside_availability",
                )

    lock_key = f"caregiver:{caregiver.pk}:schedule"
    with redis_lock(lock_key):
        with transaction.atomic():
            if shifts_overlap(
                caregiver_id=caregiver.pk,
                starts_at=starts_at,
                ends_at=ends_at,
            ):
                raise ShiftOverlapError(
                    "This time window overlaps an existing booked shift.",
                )
            return Shift.objects.create(
                caregiver=caregiver,
                patient=patient,
                availability_slot=slot,
                starts_at=starts_at,
                ends_at=ends_at,
                timezone=timezone_name or (slot.timezone if slot else "Asia/Colombo"),
                status=ShiftStatus.BOOKED,
                notes=(notes or "").strip(),
            )


def cancel_shift(*, actor, shift_id: int) -> Shift:
    try:
        shift = Shift.objects.select_related("caregiver", "caregiver__user").get(pk=shift_id)
    except Shift.DoesNotExist as exc:
        raise NotFound("Shift not found.") from exc

    is_patient = actor.pk == shift.patient_id
    is_caregiver = (
        getattr(actor, "role", None) == Role.CAREGIVER
        and hasattr(actor, "caregiver_profile")
        and actor.caregiver_profile.pk == shift.caregiver_id
    )
    if not is_patient and not is_caregiver and getattr(actor, "role", None) != Role.ADMIN:
        raise ValidationError("You cannot cancel this shift.")

    if shift.status == ShiftStatus.CANCELLED:
        return shift

    lock_key = f"caregiver:{shift.caregiver_id}:schedule"
    with redis_lock(lock_key):
        with transaction.atomic():
            shift.status = ShiftStatus.CANCELLED
            shift.save(update_fields=["status", "updated_at"])
            return shift


def shifts_queryset_for_user(user):
    role = getattr(user, "role", None)
    if role == Role.PATIENT:
        return Shift.objects.filter(patient=user).select_related("caregiver", "caregiver__user")
    if role == Role.CAREGIVER and hasattr(user, "caregiver_profile"):
        return Shift.objects.filter(caregiver=user.caregiver_profile).select_related(
            "caregiver",
            "patient",
        )
    if role == Role.ADMIN:
        return Shift.objects.all().select_related("caregiver", "patient")
    return Shift.objects.none()
