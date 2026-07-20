"""Caregiver profile completion + activation (Step 22c)."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from .models import CaregiverProfile
from .patient_profile import ProfileCompletion, _filled


def caregiver_profile_completion(profile: CaregiverProfile) -> ProfileCompletion:
    """Weighted onboarding score; match eligibility needs approval + is_active."""
    min_percent = int(getattr(settings, "CAREGIVER_PROFILE_MIN_COMPLETION", 80))
    checks: list[tuple[str, int, bool]] = [
        ("display_name", 10, _filled(profile.display_name)),
        ("nic_id", 10, _filled(profile.nic_id)),
        ("city", 10, _filled(profile.city)),
        ("location", 12, profile.location is not None),
        ("languages", 10, bool(profile.languages)),
        ("specialties", 12, bool(profile.specialties)),
        ("care_levels", 8, bool(profile.care_levels)),
        ("certifications", 8, bool(profile.certifications)),
        ("years_experience", 8, profile.years_experience is not None),
        ("service_radius_km", 6, profile.service_radius_km is not None),
        ("bio", 8, _filled(profile.bio)),
        ("certification_docs", 8, bool(profile.certification_docs)),
    ]
    earned = sum(weight for _, weight, ok in checks if ok)
    total = sum(weight for _, weight, _ in checks)
    percent = int(round(100 * earned / total)) if total else 0
    missing = [name for name, _, ok in checks if not ok]
    onboarding_complete = percent >= min_percent
    return ProfileCompletion(
        percent=percent,
        can_request_care=onboarding_complete and profile.is_approved and profile.is_active,
        missing_fields=missing,
        min_percent=min_percent,
    )


def activate_caregiver_if_ready(profile: CaregiverProfile) -> CaregiverProfile:
    """Auto-approve and activate when onboarding is complete (if enabled)."""
    completion = caregiver_profile_completion(profile)
    if completion.percent < completion.min_percent:
        return profile
    if profile.is_active and profile.is_approved:
        return profile
    if getattr(settings, "CAREGIVER_AUTO_APPROVE", True):
        profile.is_approved = True
        profile.is_active = True
        profile.save(update_fields=["is_approved", "is_active", "updated_at"])
    return profile
