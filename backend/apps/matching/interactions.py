"""Log patient ↔ caregiver interactions for offline CF (Step 21)."""

from __future__ import annotations

from collections.abc import Sequence

from django.contrib.auth import get_user_model

from .models import INTERACTION_WEIGHTS, CaregiverProfile, Interaction, InteractionKind

User = get_user_model()


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
