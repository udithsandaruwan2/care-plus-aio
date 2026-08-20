"""Offline ranking metrics + MatchRun replay evaluation (Steps 22 / 90)."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from django.db.models import QuerySet
from django.utils import timezone

from .cf_model import CFModel, get_cf_model
from .engine import VEHMFEngine, run_match
from .models import (
    CaregiverProfile,
    Interaction,
    InteractionKind,
    MatchRun,
)


def dcg_at_k(relevances: Sequence[float], k: int) -> float:
    k = min(k, len(relevances))
    if k <= 0:
        return 0.0
    total = 0.0
    for i in range(k):
        rel = relevances[i]
        if rel <= 0:
            continue
        total += (2**rel - 1) / math.log2(i + 2)
    return total


def ndcg_at_k(relevance_by_id: Mapping[int, float], ranked_ids: Sequence[int], k: int) -> float:
    """NDCG@k for a ranked caregiver id list against graded relevance labels."""
    if not ranked_ids or k <= 0:
        return 0.0
    gained = [float(relevance_by_id.get(cid, 0.0)) for cid in ranked_ids[:k]]
    ideal = sorted(relevance_by_id.values(), reverse=True)[:k]
    denom = dcg_at_k(ideal, k)
    if denom <= 0:
        return 0.0
    return dcg_at_k(gained, k) / denom


def average_precision(relevance_by_id: Mapping[int, float], ranked_ids: Sequence[int]) -> float:
    """Mean average precision for binary relevance (weight > 0)."""
    hits = 0
    precision_sum = 0.0
    positives = sum(1 for v in relevance_by_id.values() if v > 0)
    if positives == 0:
        return 0.0
    for i, cid in enumerate(ranked_ids, start=1):
        if relevance_by_id.get(cid, 0.0) <= 0:
            continue
        hits += 1
        precision_sum += hits / i
    return precision_sum / positives


def precision_at_k(
    relevance_by_id: Mapping[int, float], ranked_ids: Sequence[int], k: int
) -> float:
    """Fraction of the top-k that are relevant (weight > 0)."""
    if k <= 0 or not ranked_ids:
        return 0.0
    top = list(ranked_ids[:k])
    if not top:
        return 0.0
    hits = sum(1 for cid in top if relevance_by_id.get(cid, 0.0) > 0)
    return hits / len(top)


def recall_at_k(relevance_by_id: Mapping[int, float], ranked_ids: Sequence[int], k: int) -> float:
    """Fraction of relevant items recovered in the top-k."""
    positives = [cid for cid, v in relevance_by_id.items() if v > 0]
    if not positives or k <= 0:
        return 0.0
    top = set(ranked_ids[:k])
    hits = sum(1 for cid in positives if cid in top)
    return hits / len(positives)


def exposure_gini(exposure_counts: Mapping[int, int] | Sequence[int]) -> float:
    """Gini coefficient of caregiver exposure (0 = equal, 1 = monopoly)."""
    if isinstance(exposure_counts, Mapping):
        values = [float(v) for v in exposure_counts.values() if v > 0]
    else:
        values = [float(v) for v in exposure_counts if v > 0]
    n = len(values)
    if n == 0:
        return 0.0
    if n == 1:
        return 0.0
    ordered = sorted(values)
    total = sum(ordered)
    if total <= 0:
        return 0.0
    # Standard discrete Gini: (2 * sum(i * x_i) / (n * sum(x))) - (n + 1) / n
    weighted = sum((i + 1) * x for i, x in enumerate(ordered))
    return (2.0 * weighted) / (n * total) - (n + 1) / n


def catalogue_coverage(shown_ids: Sequence[int], catalogue_size: int) -> float:
    """Unique caregivers shown / catalogue size."""
    if catalogue_size <= 0:
        return 0.0
    return len(set(shown_ids)) / float(catalogue_size)


# Positive outcome kinds used as graded labels for ranking eval (Step 90).
_LABEL_KINDS = (
    InteractionKind.ACCEPT,
    InteractionKind.COMPLETE,
    InteractionKind.RATE,
)


def holdout_bounds(
    *,
    days: int = 14,
    end: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Recent causal holdout window ``[start, end]`` (not a random split)."""
    end_dt = end or timezone.now()
    if timezone.is_naive(end_dt):
        end_dt = timezone.make_aware(end_dt, UTC)
    start_dt = end_dt - timedelta(days=max(1, int(days)))
    return start_dt, end_dt


def holdout_match_runs(
    *,
    days: int = 14,
    end: datetime | None = None,
    limit: int | None = None,
) -> QuerySet[MatchRun]:
    """MatchRuns inside the held-out recent window, oldest-first for stability."""
    start_dt, end_dt = holdout_bounds(days=days, end=end)
    qs = (
        MatchRun.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt)
        .exclude(user_id__isnull=True)
        .order_by("created_at", "pk")
    )
    if limit is not None and limit > 0:
        qs = qs[: int(limit)]
    return qs


def relevance_for_run(run: MatchRun) -> dict[int, float]:
    """Graded labels from ACCEPT/COMPLETE/RATE after the run (causal outcomes)."""
    if not run.user_id:
        return {}
    rows = (
        Interaction.objects.filter(
            patient_id=run.user_id,
            kind__in=_LABEL_KINDS,
            created_at__gte=run.created_at,
            weight__gt=0,
        )
        .values_list("caregiver_id", "weight")
        .order_by("pk")
    )
    out: dict[int, float] = {}
    for caregiver_id, weight in rows:
        cid = int(caregiver_id)
        w = float(weight)
        if w <= 0:
            continue
        out[cid] = max(out.get(cid, 0.0), w)
    return out


def replay_ranked_ids(run: MatchRun, *, engine: VEHMFEngine | None = None) -> list[int]:
    """Re-run VEHMF for a stored MatchRun; return ranked caregiver ids."""
    filters = run.filters if isinstance(run.filters, dict) else {}
    stored_n = run.results.count()
    top_k = int(filters.get("top_k") or stored_n or 10)
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
        patient_id=filters.get("patient_id") or run.user_id,
        longitude=filters.get("longitude"),
        latitude=filters.get("latitude"),
        top_k=top_k,
        emergency=bool(run.emergency),
        max_distance_km=max_km_f,
        specialty=filters.get("specialty") or "",
        prefer_closer=bool(filters.get("prefer_closer")),
        hard_filter_language=bool(filters.get("hard_filter_language")),
        hard_filter_care_level=bool(filters.get("hard_filter_care_level")),
        engine=engine,
    )
    return [hit.caregiver_id for hit in out.results]


@dataclass(frozen=True)
class RankingEvalReport:
    """Aggregate metrics from replaying held-out MatchRuns."""

    n_runs: int
    n_labelled: int
    ndcg_at_5: float
    map_score: float
    recall_at_10: float
    precision_at_5: float
    catalogue_coverage: float
    exposure_gini: float
    holdout_start: datetime
    holdout_end: datetime
    cf_version: str | None
    per_run: tuple[dict[str, Any], ...]

    def as_table_rows(self) -> list[tuple[str, str]]:
        return [
            ("runs", str(self.n_runs)),
            ("labelled", str(self.n_labelled)),
            ("NDCG@5", f"{self.ndcg_at_5:.4f}"),
            ("MAP", f"{self.map_score:.4f}"),
            ("recall@10", f"{self.recall_at_10:.4f}"),
            ("precision@5", f"{self.precision_at_5:.4f}"),
            ("coverage", f"{self.catalogue_coverage:.4f}"),
            ("exposure_gini", f"{self.exposure_gini:.4f}"),
            ("holdout_start", self.holdout_start.isoformat()),
            ("holdout_end", self.holdout_end.isoformat()),
            ("cf_version", self.cf_version or "-"),
        ]


def evaluate_ranking(
    *,
    days: int = 14,
    end: datetime | None = None,
    limit: int | None = None,
    cf_model: CFModel | None = None,
    top_k_exposure: int = 10,
) -> RankingEvalReport:
    """Replay held-out MatchRuns against a CF model and aggregate IR metrics.

    Uses a recent time window (not a random split) so evaluation respects
    causality. Only runs with at least one post-run ACCEPT/COMPLETE/RATE label
    contribute to ranking metrics; exposure/coverage use all replayed runs.
    """
    start_dt, end_dt = holdout_bounds(days=days, end=end)
    runs = list(holdout_match_runs(days=days, end=end, limit=limit))
    model = cf_model if cf_model is not None else get_cf_model()
    engine = VEHMFEngine(cf_model=model)
    from .cf_model import cf_model_info

    cf_info = cf_model_info(model)

    ndcgs: list[float] = []
    maps: list[float] = []
    recalls: list[float] = []
    precisions: list[float] = []
    exposure: Counter[int] = Counter()
    shown: list[int] = []
    per_run: list[dict[str, Any]] = []

    for run in runs:
        ranked = replay_ranked_ids(run, engine=engine)
        for cid in ranked[:top_k_exposure]:
            exposure[cid] += 1
            shown.append(cid)

        labels = relevance_for_run(run)
        row: dict[str, Any] = {
            "run_id": run.pk,
            "n_ranked": len(ranked),
            "n_labels": len(labels),
        }
        if labels:
            n5 = ndcg_at_k(labels, ranked, 5)
            ap = average_precision(labels, ranked)
            r10 = recall_at_k(labels, ranked, 10)
            p5 = precision_at_k(labels, ranked, 5)
            ndcgs.append(n5)
            maps.append(ap)
            recalls.append(r10)
            precisions.append(p5)
            row.update(
                {
                    "ndcg@5": n5,
                    "map": ap,
                    "recall@10": r10,
                    "precision@5": p5,
                }
            )
        per_run.append(row)

    catalogue_size = CaregiverProfile.objects.filter(is_active=True, is_approved=True).count()
    labelled = len(ndcgs)

    def _mean(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    return RankingEvalReport(
        n_runs=len(runs),
        n_labelled=labelled,
        ndcg_at_5=_mean(ndcgs),
        map_score=_mean(maps),
        recall_at_10=_mean(recalls),
        precision_at_5=_mean(precisions),
        catalogue_coverage=catalogue_coverage(shown, catalogue_size),
        exposure_gini=exposure_gini(exposure),
        holdout_start=start_dt,
        holdout_end=end_dt,
        cf_version=cf_info.get("version"),
        per_run=tuple(per_run),
    )
