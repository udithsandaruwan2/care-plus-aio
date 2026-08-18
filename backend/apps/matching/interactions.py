"""Log patient ↔ caregiver interactions for offline CF (Step 21 / Step 76)."""

from __future__ import annotations

from collections.abc import Sequence

from django.contrib.auth import get_user_model

from .models import (
    INTERACTION_WEIGHTS,
    CaregiverProfile,
    CareRelationship,
    CareRelationshipStatus,
    CareRequest,
    CareRequestStatus,
    Interaction,
    InteractionKind,
    Review,
)

User = get_user_model()

# Metadata fingerprint so outcome rows can be backfilled idempotently.
OUTCOME_KEY = "outcome_key"


def complete_outcome_key(relationship_id: int) -> str:
    return f"complete:rel:{relationship_id}"


def rate_outcome_key(review_id: int) -> str:
    return f"rate:review:{review_id}"


def reject_outcome_key(care_request_id: int) -> str:
    return f"reject:req:{care_request_id}"


def _default_weight(kind: str, *, rating: int | None = None) -> float:
    base = INTERACTION_WEIGHTS.get(kind, 1.0)
    if kind == InteractionKind.RATE and rating is not None:
        return base * float(rating)
    return base


def log_interaction(
    patient: User,
    caregiver: CaregiverProfile | int,
    kind: str,
    *,
    weight: float | None = None,
    rating: int | None = None,
    metadata: dict | None = None,
) -> Interaction:
    """Append one interaction row (multiple views/requests are allowed)."""
    caregiver_id = caregiver if isinstance(caregiver, int) else caregiver.pk
    resolved_weight = weight if weight is not None else _default_weight(kind, rating=rating)
    return Interaction.objects.create(
        patient=patient,
        caregiver_id=caregiver_id,
        kind=kind,
        weight=resolved_weight,
        rating=rating,
        metadata=metadata or {},
    )


def has_outcome_interaction(outcome_key: str) -> bool:
    return Interaction.objects.filter(metadata__outcome_key=outcome_key).exists()


def log_interaction_once(
    patient: User,
    caregiver: CaregiverProfile | int,
    kind: str,
    *,
    outcome_key: str,
    weight: float | None = None,
    rating: int | None = None,
    metadata: dict | None = None,
) -> Interaction | None:
    """Create an outcome row unless one with the same ``outcome_key`` already exists."""
    if has_outcome_interaction(outcome_key):
        return None
    extra = dict(metadata or {})
    extra[OUTCOME_KEY] = outcome_key
    return log_interaction(
        patient,
        caregiver,
        kind,
        weight=weight,
        rating=rating,
        metadata=extra,
    )


def record_match_interactions(
    patient: User,
    caregiver_ids: Sequence[int],
    *,
    source: str = "match",
) -> int:
    """Log a VIEW for each caregiver shown in a match result list."""
    if not caregiver_ids:
        return 0
    rows = [
        Interaction(
            patient=patient,
            caregiver_id=cid,
            kind=InteractionKind.VIEW,
            weight=_default_weight(InteractionKind.VIEW),
            metadata={"source": source},
        )
        for cid in caregiver_ids
    ]
    Interaction.objects.bulk_create(rows)
    return len(rows)


def log_complete_interaction(relationship: CareRelationship) -> Interaction | None:
    """COMPLETE (weight 8.0) when a care relationship actually ends."""
    return log_interaction_once(
        relationship.patient,
        relationship.caregiver,
        InteractionKind.COMPLETE,
        outcome_key=complete_outcome_key(relationship.pk),
        metadata={"relationship_id": relationship.pk, "source": "relationship_end"},
    )


def log_rate_interaction(review: Review) -> Interaction | None:
    """RATE (weight 1.0 × stars) when a patient submits a review."""
    return log_interaction_once(
        review.patient,
        review.caregiver,
        InteractionKind.RATE,
        outcome_key=rate_outcome_key(review.pk),
        rating=int(review.rating),
        metadata={
            "review_id": review.pk,
            "relationship_id": review.relationship_id,
            "source": "review",
        },
    )


def log_reject_interaction(request: CareRequest) -> Interaction | None:
    """REJECT (weight -1.0) when a caregiver declines a hire request."""
    return log_interaction_once(
        request.patient,
        request.caregiver,
        InteractionKind.REJECT,
        outcome_key=reject_outcome_key(request.pk),
        metadata={"care_request_id": request.pk, "source": "care_request_reject"},
    )


def backfill_outcome_interactions() -> dict[str, int]:
    """Derive COMPLETE / RATE / REJECT rows from existing records. Idempotent."""
    created = {"complete": 0, "rate": 0, "reject": 0}

    ended = CareRelationship.objects.filter(
        status=CareRelationshipStatus.ENDED,
    ).select_related("patient", "caregiver")
    for rel in ended.iterator():
        if log_complete_interaction(rel) is not None:
            created["complete"] += 1

    reviews = Review.objects.select_related("patient", "caregiver")
    for review in reviews.iterator():
        if log_rate_interaction(review) is not None:
            created["rate"] += 1

    rejected = CareRequest.objects.filter(
        status=CareRequestStatus.REJECTED,
    ).select_related("patient", "caregiver")
    for req in rejected.iterator():
        if log_reject_interaction(req) is not None:
            created["reject"] += 1

    return created
