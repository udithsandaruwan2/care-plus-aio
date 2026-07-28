"""Trust score recompute from reviews + outcomes + responsiveness (Step 43)."""

from __future__ import annotations

from datetime import timedelta
from statistics import mean

from django.db.models import Avg

from .models import CareRelationship, CareRelationshipStatus, CareRequest, CareRequestStatus, CaregiverProfile, Review, ReviewStatus


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _review_component(caregiver: CaregiverProfile) -> float:
    avg_rating = (
        Review.objects.filter(caregiver=caregiver, status=ReviewStatus.APPROVED).aggregate(
            avg=Avg("rating")
        )["avg"]
    )
    if avg_rating is None:
        return 0.5
    return _clamp01(float(avg_rating) / 5.0)


def _completion_component(caregiver: CaregiverProfile) -> float:
    total = CareRelationship.objects.filter(caregiver=caregiver).count()
    if total == 0:
        return 0.5
    completed = CareRelationship.objects.filter(
        caregiver=caregiver,
        status=CareRelationshipStatus.ENDED,
    ).count()
    return _clamp01(completed / total)


def _response_component(caregiver: CaregiverProfile) -> float:
    rows = CareRequest.objects.filter(
        caregiver=caregiver,
        status__in=[CareRequestStatus.ACCEPTED, CareRequestStatus.REJECTED, CareRequestStatus.EXPIRED],
        responded_at__isnull=False,
    ).values("created_at", "responded_at")
    if not rows:
        return 0.5
    hours = []
    for row in rows:
        dt: timedelta = row["responded_at"] - row["created_at"]
        hours.append(max(0.0, dt.total_seconds() / 3600.0))
    avg_hours = mean(hours)
    # 0h -> 1.0, 24h -> 0.0 (linear decay, floor at 0).
    return _clamp01(1.0 - (avg_hours / 24.0))


def compute_trust_score(caregiver: CaregiverProfile) -> tuple[float, dict]:
    """Blend score from review, completion, and response-time components."""
    review = _review_component(caregiver)
    completion = _completion_component(caregiver)
    response = _response_component(caregiver)
    # Keep some prior trust inertia via current score.
    prior = _clamp01(float(caregiver.trust_score))
    blended = 0.45 * review + 0.25 * completion + 0.20 * response + 0.10 * prior
    score = round(_clamp01(blended), 4)
    return score, {
        "review_component": round(review, 4),
        "completion_component": round(completion, 4),
        "response_component": round(response, 4),
        "prior_component": round(prior, 4),
    }


def recompute_caregiver_trust(caregiver_id: int) -> dict:
    caregiver = CaregiverProfile.objects.get(pk=caregiver_id)
    score, components = compute_trust_score(caregiver)
    caregiver.trust_score = score
    caregiver.save(update_fields=["trust_score", "updated_at"])
    return {"caregiver_id": caregiver_id, "trust_score": score, **components}


def recompute_all_caregiver_trust() -> dict:
    updated = 0
    for caregiver_id in CaregiverProfile.objects.values_list("id", flat=True):
        recompute_caregiver_trust(caregiver_id)
        updated += 1
    return {"updated": updated}
