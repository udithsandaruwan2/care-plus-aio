"""Learned VEHMF fusion weights by context segment (Step 101).

Segments are ``(urgency, geo)`` with urgency ∈ {routine, emergency} and
geo ∈ {urban, rural}. Each segment with enough accept-labelled MatchRuns
fits a non-negative weight vector on stored MatchResult factor rows
(cbf, cf, geo, trust), regularized toward the AHP prior. Sparse segments
keep the AHP vector. Promotion is gated on holdout NDCG@5.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import numpy as np
from django.conf import settings
from django.utils import timezone

from apps.matching.ahp import FACTORS, get_ahp_weights, normalize_weights
from apps.matching.models import MatchResult, MatchRun, PatientProfile

Urgency = Literal["routine", "emergency"]
GeoSeg = Literal["urban", "rural"]
SegmentKey = str  # e.g. "routine_urban"

URBAN_CITIES = frozenset(
    {
        "colombo",
        "dehiwala",
        "moratuwa",
        "negombo",
        "gampaha",
        "kalutara",
    }
)

SEGMENT_KEYS: tuple[SegmentKey, ...] = (
    "routine_urban",
    "routine_rural",
    "emergency_urban",
    "emergency_rural",
)


def weights_artifact_dir() -> Path:
    raw = getattr(settings, "WEIGHTS_ARTIFACT_DIR", "") or ""
    if raw:
        path = Path(raw)
    else:
        from apps.matching.cf_model import cf_artifact_dir

        path = cf_artifact_dir().parent / "fusion_weights"
    path.mkdir(parents=True, exist_ok=True)
    return path


def min_segment_labels() -> int:
    return int(getattr(settings, "WEIGHTS_MIN_SEGMENT_LABELS", 8) or 8)


def promote_margin() -> float:
    return float(getattr(settings, "WEIGHTS_PROMOTE_MARGIN", 0.01) or 0.01)


def holdout_days() -> int:
    return int(getattr(settings, "WEIGHTS_HOLDOUT_DAYS", 14) or 14)


def gated_promotion() -> bool:
    return bool(getattr(settings, "WEIGHTS_GATED_PROMOTION", True))


def infer_geo_segment(city: str | None) -> GeoSeg | None:
    """Return urban/rural, or None when city is unknown (sparse → AHP)."""
    name = (city or "").strip().lower()
    if not name:
        return None
    if name in URBAN_CITIES:
        return "urban"
    return "rural"


def segment_key(*, emergency: bool, geo: GeoSeg | None) -> SegmentKey | None:
    if geo is None:
        return None
    urgency: Urgency = "emergency" if emergency else "routine"
    return f"{urgency}_{geo}"


def city_for_run(run: MatchRun) -> str:
    filters = run.filters if isinstance(run.filters, dict) else {}
    if run.user_id:
        profile = PatientProfile.objects.filter(user_id=run.user_id).first()
        if profile and (profile.city or "").strip():
            return profile.city.strip()
    city = (filters.get("city") or "").strip()
    if city:
        return city
    return ""


def resolve_segment(run: MatchRun) -> SegmentKey | None:
    return segment_key(emergency=bool(run.emergency), geo=infer_geo_segment(city_for_run(run)))


@dataclass(frozen=True)
class SegmentExample:
    run_id: int
    caregiver_ids: list[int]
    features: np.ndarray  # (N, 4)
    labels: dict[int, float]
    created_at: datetime


def _collect_examples(
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[SegmentKey, list[SegmentExample]]:
    from apps.matching.cf_eval import relevance_for_run

    end = end or timezone.now()
    qs = (
        MatchRun.objects.filter(created_at__lte=end)
        .exclude(user_id__isnull=True)
        .prefetch_related("results")
        .order_by("created_at", "pk")
    )
    if start is not None:
        qs = qs.filter(created_at__gte=start)

    by_seg: dict[SegmentKey, list[SegmentExample]] = defaultdict(list)
    for run in qs.iterator(chunk_size=200):
        labels = relevance_for_run(run)
        if not labels:
            continue
        seg = resolve_segment(run)
        if seg is None:
            continue
        hits = list(run.results.all())
        if len(hits) < 2:
            continue
        ids = [int(h.caregiver_id) for h in hits]
        feats = np.asarray(
            [[float(h.cbf), float(h.cf), float(h.geo), float(h.trust)] for h in hits],
            dtype=np.float64,
        )
        by_seg[seg].append(
            SegmentExample(
                run_id=int(run.pk),
                caregiver_ids=ids,
                features=feats,
                labels=labels,
                created_at=run.created_at,
            )
        )
    return by_seg


def fit_weights(
    examples: list[SegmentExample],
    prior: np.ndarray,
    *,
    epochs: int = 50,
    lr: float = 0.35,
    prior_strength: float = 0.2,
) -> np.ndarray:
    """Pairwise logistic fit: accepted caregivers should outscore others in-run."""
    W = np.asarray(prior, dtype=np.float64).copy()
    if not examples:
        return normalize_weights(W)

    for _ in range(epochs):
        grad = prior_strength * (prior - W)
        for ex in examples:
            scores = ex.features @ W
            for i, cid in enumerate(ex.caregiver_ids):
                yi = float(ex.labels.get(cid, 0.0))
                if yi <= 0:
                    continue
                for j, oid in enumerate(ex.caregiver_ids):
                    if i == j:
                        continue
                    yj = float(ex.labels.get(oid, 0.0))
                    if yj >= yi:
                        continue
                    diff = float(scores[i] - scores[j])
                    # sigmoid(-diff) → push toward larger margin
                    sig = 1.0 / (1.0 + math.exp(min(20.0, max(-20.0, diff))))
                    grad += sig * (ex.features[i] - ex.features[j]) * yi
        W = np.maximum(W + lr * grad / max(len(examples), 1), 0.0)
        W = np.asarray(normalize_weights(W), dtype=np.float64)
    return W


def ndcg_for_examples(examples: list[SegmentExample], weights: np.ndarray) -> float:
    from apps.matching.cf_eval import ndcg_at_k

    if not examples:
        return 0.0
    scores = []
    W = np.asarray(weights, dtype=np.float64)
    for ex in examples:
        raw = ex.features @ W
        order = np.argsort(-raw)
        ranked = [ex.caregiver_ids[int(i)] for i in order]
        scores.append(ndcg_at_k(ex.labels, ranked, 5))
    return float(sum(scores) / len(scores))


def _split_holdout(
    examples: list[SegmentExample],
) -> tuple[list[SegmentExample], list[SegmentExample]]:
    if len(examples) < 4:
        return examples, examples
    # Time-ordered: last ~30% holdout
    cut = max(1, int(len(examples) * 0.7))
    return examples[:cut], examples[cut:]


@dataclass
class SegmentFitResult:
    key: SegmentKey
    vector: tuple[float, float, float, float]
    source: str  # learned | ahp
    reason: str
    n_train: int
    n_holdout: int
    ndcg_learned: float
    ndcg_ahp: float
    promoted: bool


def train_segment(
    key: SegmentKey,
    examples: list[SegmentExample],
    *,
    force: bool = False,
) -> SegmentFitResult:
    emergency = key.startswith("emergency_")
    prior = np.asarray(get_ahp_weights(emergency=emergency), dtype=np.float64)
    ahp_vec = tuple(float(x) for x in prior)

    if len(examples) < min_segment_labels():
        return SegmentFitResult(
            key=key,
            vector=ahp_vec,
            source="ahp",
            reason="sparse",
            n_train=len(examples),
            n_holdout=0,
            ndcg_learned=0.0,
            ndcg_ahp=0.0,
            promoted=False,
        )

    train, hold = _split_holdout(examples)
    learned = fit_weights(train, prior)
    n_ahp = ndcg_for_examples(hold, prior)
    n_learned = ndcg_for_examples(hold, learned)

    promote = force or (not gated_promotion()) or (n_learned >= n_ahp + promote_margin())
    if promote:
        return SegmentFitResult(
            key=key,
            vector=tuple(float(x) for x in learned),
            source="learned",
            reason="holdout_improved" if n_learned >= n_ahp + promote_margin() else "forced",
            n_train=len(train),
            n_holdout=len(hold),
            ndcg_learned=n_learned,
            ndcg_ahp=n_ahp,
            promoted=True,
        )
    return SegmentFitResult(
        key=key,
        vector=ahp_vec,
        source="ahp",
        reason="holdout_regressed",
        n_train=len(train),
        n_holdout=len(hold),
        ndcg_learned=n_learned,
        ndcg_ahp=n_ahp,
        promoted=False,
    )


def train_fusion_weights(*, force: bool = False, end: datetime | None = None) -> dict[str, Any]:
    """Fit all segments, write artifact, return summary."""
    end = end or timezone.now()
    start = end - timedelta(days=holdout_days() * 3)  # train window ≈ 3× holdout days
    by_seg = _collect_examples(start=start, end=end)

    segments: dict[str, Any] = {}
    results: list[SegmentFitResult] = []
    for key in SEGMENT_KEYS:
        fit = train_segment(key, by_seg.get(key, []), force=force)
        results.append(fit)
        segments[key] = {
            "vector": list(fit.vector),
            "source": fit.source,
            "reason": fit.reason,
            "n_train": fit.n_train,
            "n_holdout": fit.n_holdout,
            "ndcg_at_5_learned": round(fit.ndcg_learned, 6),
            "ndcg_at_5_ahp": round(fit.ndcg_ahp, 6),
            "promoted": fit.promoted,
        }

    version = timezone.now().strftime("%Y%m%d%H%M%S")
    doc = {
        "version": version,
        "factors": list(FACTORS),
        "trained_at": timezone.now().isoformat(),
        "segments": segments,
        "ahp_fallback": {
            "vector": list(get_ahp_weights()),
            "emergency_vector": list(get_ahp_weights(emergency=True)),
        },
        "settings": {
            "min_segment_labels": min_segment_labels(),
            "promote_margin": promote_margin(),
            "gated": gated_promotion(),
        },
    }
    root = weights_artifact_dir()
    version_dir = root / f"v{version}"
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / "weights.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    (root / "current.json").write_text(
        json.dumps({"version": version, "dir": f"v{version}"}, indent=2),
        encoding="utf-8",
    )
    reset_learned_weights_cache()
    from apps.matching.ahp import reset_ahp_cache

    reset_ahp_cache()
    return {
        "version": version,
        "segments": segments,
        "learned_count": sum(1 for r in results if r.source == "learned"),
        "ahp_fallback_count": sum(1 for r in results if r.source == "ahp"),
        "artifact_dir": str(version_dir),
    }


_LEARNED_CACHE: dict[str, Any] | None = None


def reset_learned_weights_cache() -> None:
    global _LEARNED_CACHE
    _LEARNED_CACHE = None


def load_learned_weights_doc(*, force: bool = False) -> dict[str, Any] | None:
    global _LEARNED_CACHE
    if _LEARNED_CACHE is not None and not force:
        return _LEARNED_CACHE
    pointer = weights_artifact_dir() / "current.json"
    if not pointer.exists():
        _LEARNED_CACHE = None
        return None
    meta = json.loads(pointer.read_text(encoding="utf-8"))
    path = weights_artifact_dir() / meta["dir"] / "weights.json"
    if not path.exists():
        _LEARNED_CACHE = None
        return None
    _LEARNED_CACHE = json.loads(path.read_text(encoding="utf-8"))
    return _LEARNED_CACHE


def get_fusion_weights(
    *,
    emergency: bool = False,
    city: str | None = None,
    refresh: bool = False,
) -> tuple[tuple[float, float, float, float], str]:
    """Return ``(weights, source)`` for the active segment or AHP fallback.

    Source strings: ``ahp``, ``ahp_emergency``, ``learned:routine_urban``, …
    """
    geo = infer_geo_segment(city)
    key = segment_key(emergency=emergency, geo=geo)
    ahp = get_ahp_weights(emergency=emergency, refresh=refresh)
    ahp_source = "ahp_emergency" if emergency else "ahp"
    if key is None:
        return tuple(float(x) for x in ahp), ahp_source  # type: ignore[return-value]

    doc = load_learned_weights_doc(force=refresh)
    if not doc:
        return tuple(float(x) for x in ahp), ahp_source  # type: ignore[return-value]

    seg = (doc.get("segments") or {}).get(key) or {}
    if seg.get("source") != "learned" or not seg.get("vector"):
        return tuple(float(x) for x in ahp), ahp_source  # type: ignore[return-value]

    try:
        vec = normalize_weights(seg["vector"])
    except Exception:
        return tuple(float(x) for x in ahp), ahp_source  # type: ignore[return-value]
    return vec, f"learned:{key}"


def fusion_weights_report() -> dict[str, Any]:
    """Payload fragment for GET /match/weights/."""
    doc = load_learned_weights_doc()
    routine, routine_src = get_fusion_weights(emergency=False, city="Colombo")
    emergency, emergency_src = get_fusion_weights(emergency=True, city="Colombo")
    rural, rural_src = get_fusion_weights(emergency=False, city="Kandy")
    return {
        "learned": None
        if doc is None
        else {
            "version": doc.get("version"),
            "segments": doc.get("segments"),
            "trained_at": doc.get("trained_at"),
        },
        "active": {
            "routine_urban": {"vector": list(routine), "source": routine_src},
            "routine_rural": {"vector": list(rural), "source": rural_src},
            "emergency_urban": {"vector": list(emergency), "source": emergency_src},
        },
        "consistency_ratio_source": "ahp",
    }
