"""Helpers to enqueue FAISS refresh when embed-relevant caregiver fields change."""

from __future__ import annotations

from .models import CaregiverProfile

# Fields that feed ``profile_to_text`` / index membership (Step 89).
EMBED_RELEVANT_FIELDS = (
    "display_name",
    "specialties",
    "certifications",
    "languages",
    "care_levels",
    "bio",
    "is_active",
)


def embed_fingerprint(profile: CaregiverProfile) -> tuple:
    """Comparable snapshot of embed-relevant profile state."""
    return (
        profile.display_name or "",
        tuple(profile.specialties or []),
        tuple(profile.certifications or []),
        tuple(profile.languages or []),
        tuple(profile.care_levels or []),
        profile.bio or "",
        bool(profile.is_active),
    )


def enqueue_embedding_refresh(caregiver_id: int) -> None:
    """Async re-embed + FAISS rebuild for one caregiver (eager-safe)."""
    from django.conf import settings

    from .tasks import refresh_caregiver_embedding

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        refresh_caregiver_embedding(caregiver_id)
        return
    refresh_caregiver_embedding.delay(caregiver_id)


def maybe_enqueue_embedding_refresh(
    before: tuple | None,
    after_profile: CaregiverProfile,
) -> bool:
    """Enqueue when fingerprint changed. Returns True if a refresh was queued."""
    after = embed_fingerprint(after_profile)
    if before is not None and before == after:
        return False
    enqueue_embedding_refresh(after_profile.pk)
    return True
