"""Replay a stored MatchRun against the current VEHMF artifacts (Step 79)."""

from __future__ import annotations

from apps.matching.engine import match_run_provenance, run_match
from apps.matching.models import MatchRun


def replay_match_run(run: MatchRun) -> dict:
    """Re-run VEHMF with the recorded inputs and compare ranking + artifacts."""
    filters = run.filters if isinstance(run.filters, dict) else {}
    stored = list(run.results.order_by("rank").values_list("caregiver_id", flat=True))
    top_k = int(filters.get("top_k") or len(stored) or 10)
    max_km = filters.get("max_distance_km")
    try:
        max_km_f = float(max_km) if max_km is not None else None
    except (TypeError, ValueError):
        max_km_f = None

    out = run_match(
        condition=run.condition or filters.get("condition") or "",
        language=run.language or filters.get("language") or "",
        care_level=run.care_level or filters.get("care_level") or "",
        query=run.query or filters.get("query") or "",
        patient_id=filters.get("patient_id") or (run.user_id if run.user_id else None),
        longitude=filters.get("longitude"),
        latitude=filters.get("latitude"),
        top_k=top_k,
        emergency=bool(run.emergency),
        max_distance_km=max_km_f,
        specialty=filters.get("specialty") or "",
        prefer_closer=bool(filters.get("prefer_closer")),
        hard_filter_language=bool(filters.get("hard_filter_language")),
        hard_filter_care_level=bool(filters.get("hard_filter_care_level")),
    )
    replayed = [hit.caregiver_id for hit in out.results]
    prov = match_run_provenance(out)
    artifacts_match = (
        (prov["index_version"] or "") == (run.index_version or "")
        and (prov["cf_version"] or "") == (run.cf_version or "")
        and (prov["embedding_backend"] or "") == (run.embedding_backend or "")
    )
    ranking_match = stored == replayed
    reasons: list[str] = []
    if not artifacts_match:
        reasons.append(
            "artifacts_changed: "
            f"stored index={run.index_version or '-'} cf={run.cf_version or '-'} "
            f"emb={run.embedding_backend or '-'} "
            f"now index={prov['index_version'] or '-'} cf={prov['cf_version'] or '-'} "
            f"emb={prov['embedding_backend'] or '-'}"
        )
    if not ranking_match:
        reasons.append(f"ranking_changed: stored={stored} replayed={replayed}")
    return {
        "run_id": run.pk,
        "ok": artifacts_match and ranking_match,
        "artifacts_match": artifacts_match,
        "ranking_match": ranking_match,
        "stored_ids": stored,
        "replayed_ids": replayed,
        "reasons": reasons,
        "provenance": prov,
    }
