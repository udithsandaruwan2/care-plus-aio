"""Emergency re-match orchestration from health-critical events (Step 47)."""

from __future__ import annotations

import time

from django.db import transaction

from apps.accounts.notifications.push_dispatch import notify_health_critical_mobile
from apps.health_monitoring.models import HealthEvent

from .engine import run_match
from .interactions import record_match_interactions
from .models import CaregiverProfile, MatchResult, create_match_run
from .push import push_match_results


@transaction.atomic
def emergency_rematch_for_health_event(event: HealthEvent) -> dict:
    """Run emergency VEHMF rematch and push nearest advanced caregiver."""
    patient = event.patient
    profile = getattr(patient, "patient_profile", None)
    lon = lat = None
    if profile is not None and profile.location is not None:
        lon, lat = profile.location.x, profile.location.y

    t0 = time.perf_counter()
    out = run_match(
        condition="",
        language=(profile.preferred_language if profile else ""),
        care_level="advanced",
        query="emergency critical health event",
        patient_id=patient.pk,
        longitude=lon,
        latitude=lat,
        top_k=15,
        emergency=True,
        prefer_closer=True,
        hard_filter_care_level=True,
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)

    profiles = {
        p.id: p
        for p in CaregiverProfile.objects.filter(
            id__in=[r.caregiver_id for r in out.results],
            is_available=True,
        ).select_related("user")
    }

    # Step 47 acceptance: prioritize nearest certified advanced caregiver.
    selected = None
    for hit in out.results:
        p = profiles.get(hit.caregiver_id)
        if p and p.certifications and "advanced" in p.care_levels:
            selected = hit
            break
    if selected is None and out.results:
        selected = out.results[0]
    if selected is None:
        return {"created": False, "reason": "no_match"}

    run = create_match_run(
        user=patient,
        query=out.query,
        condition="",
        language=(profile.preferred_language if profile else ""),
        care_level="advanced",
        emergency=True,
        weights=list(out.weights),
        latency_ms=latency_ms,
        source="emergency_rematch",
    )
    chosen_profile = profiles.get(selected.caregiver_id)
    MatchResult.objects.create(
        run=run,
        caregiver_id=selected.caregiver_id,
        rank=1,
        score=selected.score,
        cbf=selected.cbf,
        cf=selected.cf,
        geo=selected.geo,
        trust=selected.trust,
        explanation=selected.explanation,
        distance_m=selected.distance_m,
    )
    record_match_interactions(patient, [selected.caregiver_id], source="health_emergency_rematch")

    payload = {
        "request_id": run.pk,
        "latency_ms": latency_ms,
        "query": out.query,
        "emergency": True,
        "cf_enabled": out.cf_enabled,
        "cf_version": out.cf_version,
        "weights": {
            "cbf": round(out.weights[0], 6),
            "cf": round(out.weights[1], 6),
            "geo": round(out.weights[2], 6),
            "trust": round(out.weights[3], 6),
        },
        "results": [
            {
                "caregiver_id": selected.caregiver_id,
                "rank": 1,
                "score": round(selected.score, 6),
                "breakdown": {
                    "cbf": round(selected.cbf, 6),
                    "cf": round(selected.cf, 6),
                    "geo": round(selected.geo, 6),
                    "trust": round(selected.trust, 6),
                },
                "explanation": selected.explanation,
                "distance_m": None if selected.distance_m is None else round(selected.distance_m, 1),
                "display_name": chosen_profile.display_name if chosen_profile else "",
                "specialties": chosen_profile.specialties if chosen_profile else [],
                "languages": chosen_profile.languages if chosen_profile else [],
                "care_levels": chosen_profile.care_levels if chosen_profile else [],
                "trust_score": chosen_profile.trust_score if chosen_profile else None,
                "is_available": bool(chosen_profile.is_available) if chosen_profile else False,
            }
        ],
        "emergency_context": {
            "event_id": event.pk,
            "event_type": event.event_type,
            "rule_key": event.rule_key,
            "window_end": event.window_end.isoformat(),
        },
    }
    push_match_results(patient.pk, payload)
    notify_health_critical_mobile(
        user=patient,
        event_id=event.pk,
        caregiver_id=selected.caregiver_id,
        match_run_id=run.pk,
    )
    event.rematch_run = run
    event.handled_at = run.created_at
    event.payload = {**(event.payload or {}), "dispatched": True}
    event.save(update_fields=["rematch_run", "handled_at", "payload_ciphertext"])
    return {"created": True, "run_id": run.pk, "caregiver_id": selected.caregiver_id}

