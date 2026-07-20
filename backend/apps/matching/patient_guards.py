"""Guards for patient-only actions (Step 22b)."""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import Role

from .patient_profile import patient_profile_completion


def ensure_patient_can_request_care(user) -> None:
    """Raise when a patient profile is below the completion threshold."""
    if getattr(user, "role", None) != Role.PATIENT:
        return
    try:
        profile = user.patient_profile
    except Exception as exc:
        raise PermissionDenied(
            "Complete your patient profile before requesting care."
        ) from exc
    completion = patient_profile_completion(profile)
    if not completion.can_request_care:
        raise PermissionDenied(
            {
                "detail": (
                    f"Patient profile is {completion.percent}% complete; "
                    f"need at least {completion.min_percent}% to request care."
                ),
                "completion_percent": completion.percent,
                "missing_fields": completion.missing_fields,
            }
        )
