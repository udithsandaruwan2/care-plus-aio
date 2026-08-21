"""Ranking guardrails: MMR diversity, exposure caps, fairness report (Step 103).

Unapproved caregivers are filtered in the engine pool. This module handles
diversity re-ranking (MMR on language/specialty tokens), rolling exposure
caps, and an offline fairness report by language and city.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db.models import Count
from django.utils import timezone

if TYPE_CHECKING:
    from apps.matching.engine import RankedMatch
    from apps.matching.models import CaregiverProfile


def mmr_lambda() -> float:
    try:
        return max(0.0, min(1.0, float(getattr(settings, "MATCH_MMR_LAMBDA", 0.7))))
    except (TypeError, ValueError):
        return 0.7


def exposure_cap() -> int:
    try:
        return max(0, int(getattr(settings, "MATCH_EXPOSURE_CAP", 50)))
    except (TypeError, ValueError):
        return 50


def exposure_window_hours() -> int:
    try:
        return max(1, int(getattr(settings, "MATCH_EXPOSURE_WINDOW_HOURS", 24)))
    except (TypeError, ValueError):
        return 24


def profile_tokens(profile: CaregiverProfile) -> frozenset[str]:
    """Language + specialty tokens used for diversity similarity."""
    toks: set[str] = set()
    for lang in profile.languages or []:
        s = str(lang).strip().lower()
        if s:
            toks.add(f"lang:{s}")
    for spec in profile.specialties or []:
        s = str(spec).strip().lower()
        if s:
            toks.add(f"spec:{s}")
    return frozenset(toks)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def mmr_rerank(
    candidates: Sequence[RankedMatch],
    profiles: Mapping[int, CaregiverProfile],
    *,
    k: int,
    lambda_: float | None = None,
) -> list[RankedMatch]:
    """Greedy MMR: λ·relevance − (1−λ)·max similarity to already selected."""
    if k <= 0 or not candidates:
        return []
    lam = mmr_lambda() if lambda_ is None else max(0.0, min(1.0, float(lambda_)))
    # Relevance in [0, 1] from current score order (already fusion scores).
    scores = [float(c.score) for c in candidates]
    lo, hi = min(scores), max(scores)
    span = hi - lo
    rel = {
        c.caregiver_id: (1.0 if span <= 0 else (float(c.score) - lo) / span) for c in candidates
    }
    token_map = {
        c.caregiver_id: profile_tokens(profiles[c.caregiver_id])
        for c in candidates
        if c.caregiver_id in profiles
    }
    remaining = {c.caregiver_id: c for c in candidates}
    selected: list[RankedMatch] = []
    selected_ids: list[int] = []

    while remaining and len(selected) < k:
        best_id = None
        best_val = float("-inf")
        for cid, hit in remaining.items():
            toks = token_map.get(cid, frozenset())
            max_sim = 0.0
            for sid in selected_ids:
                max_sim = max(max_sim, jaccard(toks, token_map.get(sid, frozenset())))
            val = lam * rel.get(cid, 0.0) - (1.0 - lam) * max_sim
            if val > best_val:
                best_val = val
                best_id = cid
        if best_id is None:
            break
        selected.append(replace(remaining[best_id], was_exploratory=False))
        selected_ids.append(best_id)
        del remaining[best_id]
    return selected


def exposure_counts_in_window(
    caregiver_ids: Sequence[int],
    *,
    window_hours: int | None = None,
) -> dict[int, int]:
    """How often each caregiver appeared in MatchResult within the rolling window."""
    from apps.matching.models import MatchResult

    ids = [int(x) for x in caregiver_ids]
    if not ids:
        return {}
    hours = exposure_window_hours() if window_hours is None else max(1, int(window_hours))
    since = timezone.now() - timedelta(hours=hours)
    rows = (
        MatchResult.objects.filter(caregiver_id__in=ids, run__created_at__gte=since)
        .values("caregiver_id")
        .annotate(n=Count("id"))
    )
    return {int(r["caregiver_id"]): int(r["n"]) for r in rows}


def filter_overexposed(
    candidates: Sequence[RankedMatch],
    *,
    cap: int | None = None,
    window_hours: int | None = None,
    emergency: bool = False,
) -> tuple[list[RankedMatch], list[int]]:
    """Drop caregivers at/above the rolling exposure cap (skipped in emergencies)."""
    limit = exposure_cap() if cap is None else max(0, int(cap))
    if emergency or limit <= 0 or not candidates:
        return list(candidates), []
    counts = exposure_counts_in_window(
        [c.caregiver_id for c in candidates],
        window_hours=window_hours,
    )
    kept: list[RankedMatch] = []
    dropped: list[int] = []
    for c in candidates:
        if counts.get(c.caregiver_id, 0) >= limit:
            dropped.append(c.caregiver_id)
        else:
            kept.append(c)
    # Never empty the list solely due to caps — keep highest-scoring if all capped.
    if not kept and candidates:
        return [candidates[0]], dropped
    return kept, dropped


def diversity_stats(hits: Sequence[RankedMatch], profiles: Mapping[int, CaregiverProfile]) -> dict[str, Any]:
    langs: set[str] = set()
    specs: set[str] = set()
    for h in hits:
        p = profiles.get(h.caregiver_id)
        if not p:
            continue
        for lang in p.languages or []:
            langs.add(str(lang).lower())
        for spec in p.specialties or []:
            specs.add(str(spec).lower())
    return {
        "n": len(hits),
        "unique_languages": len(langs),
        "unique_specialties": len(specs),
        "languages": sorted(langs),
        "specialties": sorted(specs),
    }


def build_fairness_report(*, days: int = 14) -> dict[str, Any]:
    """Exposure by city and language over recent MatchResults."""
    from apps.matching.cf_eval import exposure_gini
    from apps.matching.models import MatchResult

    days = max(1, min(int(days), 365))
    since = timezone.now() - timedelta(days=days)
    rows = list(
        MatchResult.objects.filter(run__created_at__gte=since)
        .select_related("caregiver")
        .values_list(
            "caregiver_id",
            "caregiver__city",
            "caregiver__languages",
        )
    )
    by_city: Counter[str] = Counter()
    by_lang: Counter[str] = Counter()
    by_cg: Counter[int] = Counter()
    for cid, city, languages in rows:
        by_cg[int(cid)] += 1
        by_city[(city or "unknown").strip() or "unknown"] += 1
        langs = languages or []
        if not langs:
            by_lang["(none)"] += 1
        else:
            # Count primary language once per appearance.
            by_lang[str(langs[0]).strip() or "(none)"] += 1

    return {
        "window_days": days,
        "n_impressions": len(rows),
        "n_unique_caregivers": len(by_cg),
        "exposure_gini": round(exposure_gini(by_cg), 6),
        "by_city": [
            {"city": k, "count": v, "share": round(v / len(rows), 4) if rows else 0.0}
            for k, v in by_city.most_common()
        ],
        "by_language": [
            {"language": k, "count": v, "share": round(v / len(rows), 4) if rows else 0.0}
            for k, v in by_lang.most_common()
        ],
    }
