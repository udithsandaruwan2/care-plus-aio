"""Step 53 — VEHMF next-best caregiver when a shift booking collides."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime

from django.db import transaction

from apps.matching.engine import run_match
from apps.matching.interactions import record_match_interactions
from apps.matching.models import (
    CaregiverAvailabilitySlot,
    CaregiverProfile,
    MatchResult,
    create_match_run,
)
from apps.matching.shifts import _slot_covers_window, shifts_overlap


@dataclass(frozen=True)
class ConflictFallbackOffer:
    caregiver_id: int
    display_name: str
    score: float
    explanation: str
    distance_m: float | None
    availability_slot_id: int
    starts_at: datetime
    ends_at: datetime
    match_run_id: int
    specialties: list[str]
    languages: list[str]
    care_levels: list[str]
    trust_score: float | None

    def as_dict(self) -> dict:
        return {
            "caregiver_id": self.caregiver_id,
            "display_name": self.display_name,
            "score": round(self.score, 6),
            "explanation": self.explanation,
            "distance_m": None if self.distance_m is None else round(self.distance_m, 1),
            "availability_slot_id": self.availability_slot_id,
            "starts_at": self.starts_at.isoformat(),
            "ends_at": self.ends_at.isoformat(),
            "match_run_id": self.match_run_id,
            "specialties": self.specialties,
            "languages": self.languages,
            "care_levels": self.care_levels,
            "trust_score": self.trust_score,
        }


@transaction.atomic
def find_shift_conflict_fallback(
    *,
    patient,
    exclude_caregiver_id: int,
    starts_at: datetime,
    ends_at: datetime,
    top_k: int = 15,
) -> ConflictFallbackOffer | None:
    """
    Rank caregivers with VEHMF and return the first who:
    - is not the conflicting caregiver
    - is active + soft-available
    - has a weekly slot covering the requested window
    - has no overlapping booked shift
    """
    profile = getattr(patient, "patient_profile", None)
    lon = lat = None
    if profile is not None and profile.location is not None:
        lon, lat = profile.location.x, profile.location.y

    language = (profile.preferred_language if profile else "") or ""
    care_level = (profile.care_level if profile else "") or ""
    conditions = list(profile.conditions or []) if profile else []
    condition = conditions[0] if conditions else ""

    t0 = time.perf_counter()
    out = run_match(
        condition=condition,
        language=language,
        care_level=care_level,
        query="schedule conflict fallback",
        patient_id=patient.pk,
        longitude=lon,
        latitude=lat,
        top_k=top_k,
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)

    run = create_match_run(
        user=patient,
        query=out.query,
        condition=condition,
        language=language,
        care_level=care_level,
        emergency=False,
        weights=list(out.weights),
        latency_ms=latency_ms,
        source="conflict_fallback",
    )

    ranked_ids = [hit.caregiver_id for hit in out.results]
    profiles = {
        p.id: p
        for p in CaregiverProfile.objects.filter(
            id__in=ranked_ids,
            is_active=True,
            is_available=True,
        ).select_related("user")
    }

    for rank, hit in enumerate(out.results, start=1):
        MatchResult.objects.create(
            run=run,
            caregiver_id=hit.caregiver_id,
            rank=rank,
            score=hit.score,
            cbf=hit.cbf,
            cf=hit.cf,
            geo=hit.geo,
            trust=hit.trust,
            explanation=hit.explanation,
            distance_m=hit.distance_m,
        )

        if hit.caregiver_id == exclude_caregiver_id:
            continue
        cg = profiles.get(hit.caregiver_id)
        if cg is None:
            continue

        covering = [
            slot
            for slot in CaregiverAvailabilitySlot.objects.filter(
                caregiver_id=cg.pk,
                is_active=True,
            )
            if _slot_covers_window(slot=slot, starts_at=starts_at, ends_at=ends_at)
        ]
        if not covering:
            continue
        if shifts_overlap(caregiver_id=cg.pk, starts_at=starts_at, ends_at=ends_at):
            continue

        record_match_interactions(
            patient,
            [cg.pk],
            source="schedule_conflict_fallback",
        )
        return ConflictFallbackOffer(
            caregiver_id=cg.pk,
            display_name=cg.display_name,
            score=hit.score,
            explanation=hit.explanation,
            distance_m=hit.distance_m,
            availability_slot_id=covering[0].pk,
            starts_at=starts_at,
            ends_at=ends_at,
            match_run_id=run.pk,
            specialties=list(cg.specialties or []),
            languages=list(cg.languages or []),
            care_levels=list(cg.care_levels or []),
            trust_score=cg.trust_score,
        )

    return None
