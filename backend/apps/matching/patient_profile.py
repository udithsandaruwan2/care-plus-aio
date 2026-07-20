"""Patient profile completion helpers (Step 22b)."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from .models import PatientProfile


@dataclass(frozen=True)
class ProfileCompletion:
    percent: int
    can_request_care: bool
    missing_fields: list[str]
    min_percent: int


def _filled(value: str | None) -> bool:
    return bool((value or "").strip())


def patient_profile_completion(profile: PatientProfile) -> ProfileCompletion:
    """Weighted completion score used to gate hire/request actions."""
    min_percent = int(getattr(settings, "PATIENT_PROFILE_MIN_COMPLETION", 80))
    checks: list[tuple[str, int, bool]] = [
        ("display_name", 10, _filled(profile.display_name)),
        ("city", 10, _filled(profile.city)),
        ("location", 12, profile.location is not None),
        ("preferred_language", 8, _filled(profile.preferred_language)),
        ("languages", 8, bool(profile.languages)),
        ("care_level", 8, _filled(profile.care_level)),
        ("conditions", 12, bool(profile.conditions)),
        ("height_cm", 8, profile.height_cm is not None),
        ("weight_kg", 8, profile.weight_kg is not None),
        ("blood_type", 8, _filled(profile.blood_type)),
        ("emergency_contact_name", 8, _filled(profile.emergency_contact_name)),
        ("emergency_contact_phone", 10, _filled(profile.emergency_contact_phone)),
    ]
    earned = sum(weight for _, weight, ok in checks if ok)
    total = sum(weight for _, weight, _ in checks)
    percent = int(round(100 * earned / total)) if total else 0
    missing = [name for name, _, ok in checks if not ok]
    return ProfileCompletion(
        percent=percent,
        can_request_care=percent >= min_percent,
        missing_fields=missing,
        min_percent=min_percent,
    )
