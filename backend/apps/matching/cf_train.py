"""Offline ALS training for patient ↔ caregiver CF (Steps 21 / 91 / 92)."""

from __future__ import annotations

import json
import logging
import random
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
import scipy.sparse as sp
from django.conf import settings
from implicit.als import AlternatingLeastSquares

from .cf_model import (
    AlsCFModel,
    cf_artifact_dir,
    load_cf_model,
    load_cf_model_from_dir,
    reset_cf_cache,
    set_current_cf_pointer,
)
from .models import Interaction, InteractionKind, ModelKind, ModelVersion

logger = logging.getLogger(__name__)

# Stronger-than-view positives used when classifying pair outcomes (Step 92).
_STRONG_POSITIVE_KINDS = frozenset(
    {
        InteractionKind.REQUEST,
        InteractionKind.ACCEPT,
        InteractionKind.COMPLETE,
        InteractionKind.RATE,
    }
)

PairKind = Literal["positive", "hard_negative", "weak_negative"]


def _training_rows(
    *,
    shuffle_interactions: bool = False,
) -> list[tuple[int, int, str, float]]:
    """Load interaction rows as (patient_id, caregiver_id, kind, weight)."""
    rows = list(
        Interaction.objects.values_list("patient_id", "caregiver_id", "kind", "weight")
    )
    if shuffle_interactions and rows:
        caregivers = [r[1] for r in rows]
        rng = random.Random(0)
        rng.shuffle(caregivers)
        rows = [(r[0], caregivers[i], r[2], r[3]) for i, r in enumerate(rows)]
    return rows


def classify_pair_signals(
    rows: list[tuple[int, int, str, float]],
) -> dict[tuple[int, int], tuple[PairKind, float]]:
    """Collapse raw interactions into one labelled signal per patient↔caregiver pair.

    Priority: hard REJECT > strong positive > VIEW-only weak negative.
    """
    by_pair: dict[tuple[int, int], list[tuple[str, float]]] = defaultdict(list)
    for patient_id, caregiver_id, kind, weight in rows:
        by_pair[(int(patient_id), int(caregiver_id))].append((str(kind), float(weight)))

    out: dict[tuple[int, int], tuple[PairKind, float]] = {}
    for key, events in by_pair.items():
        kinds = {k for k, _ in events}
        if InteractionKind.REJECT in kinds:
            mag = sum(abs(w) for k, w in events if k == InteractionKind.REJECT) or 1.0
            out[key] = ("hard_negative", mag)
            continue
        strong = [(k, w) for k, w in events if k in _STRONG_POSITIVE_KINDS and w > 0]
        if strong:
            out[key] = ("positive", sum(w for _, w in strong))
            continue
        if InteractionKind.VIEW in kinds:
            view_w = sum(w for k, w in events if k == InteractionKind.VIEW and w > 0) or 1.0
            out[key] = ("weak_negative", view_w)
    return out


def build_confidence_observations(
    signals: dict[tuple[int, int], tuple[PairKind, float]],
    *,
    patient_to_idx: dict[int, int],
    caregiver_to_idx: dict[int, int],
    use_negatives: bool = True,
    positive_alpha: float = 40.0,
    reject_alpha: float = 80.0,
    weak_neg_alpha: float = 5.0,
) -> tuple[list[tuple[int, int, float, float]], dict[str, int]]:
    """Hu-style (user_idx, item_idx, confidence, preference) observations.

    When ``use_negatives`` is false, only positives are emitted (legacy ALS).
    """
    obs: list[tuple[int, int, float, float]] = []
    counts = {"positive": 0, "hard_negative": 0, "weak_negative": 0, "skipped": 0}
    for (pid, cid), (kind, magnitude) in signals.items():
        if pid not in patient_to_idx or cid not in caregiver_to_idx:
            counts["skipped"] += 1
            continue
        u = patient_to_idx[pid]
        i = caregiver_to_idx[cid]
        if kind == "positive":
            conf = 1.0 + float(positive_alpha) * float(magnitude)
            obs.append((u, i, conf, 1.0))
            counts["positive"] += 1
        elif kind == "hard_negative":
            if not use_negatives:
                counts["skipped"] += 1
                continue
            conf = 1.0 + float(reject_alpha) * float(magnitude)
            obs.append((u, i, conf, 0.0))
            counts["hard_negative"] += 1
        elif kind == "weak_negative":
            if not use_negatives:
                # Legacy: treat VIEW as a weak positive.
                conf = 1.0 + float(positive_alpha) * float(magnitude)
                obs.append((u, i, conf, 1.0))
                counts["positive"] += 1
            else:
                conf = 1.0 + float(weak_neg_alpha) * float(magnitude)
                obs.append((u, i, conf, 0.0))
                counts["weak_negative"] += 1
    return obs, counts


def fit_confidence_weighted_als(
    *,
    n_users: int,
    n_items: int,
    observations: list[tuple[int, int, float, float]],
    factors: int = 32,
    iterations: int = 15,
    regularization: float = 0.01,
    random_state: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Alternating least squares with per-observation confidence and preference (0/1).

    Hard/weak negatives use preference 0 with elevated confidence so factors are
    pushed away from rejected / shown-but-ignored caregivers (Step 92).
    """
    if not observations:
        raise ValueError("No CF observations to fit")

    rng = np.random.default_rng(random_state)
    X = rng.normal(0.0, 0.01, size=(n_users, factors)).astype(np.float64)
    Y = rng.normal(0.0, 0.01, size=(n_items, factors)).astype(np.float64)

    by_user: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
    by_item: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
    for u, i, conf, pref in observations:
        by_user[u].append((i, conf, pref))
        by_item[i].append((u, conf, pref))

    eye = np.eye(factors, dtype=np.float64) * float(regularization)

    def _solve_entity(factors_other: np.ndarray, obs: list[tuple[int, float, float]]) -> np.ndarray:
        # A = YtY + λI + Σ (c-1) y y^T ; b = Σ c p y
        yt_y = factors_other.T @ factors_other
        a = yt_y + eye
        b = np.zeros(factors, dtype=np.float64)
        for idx, conf, pref in obs:
            vec = factors_other[idx]
            a = a + (conf - 1.0) * np.outer(vec, vec)
            b = b + (conf * pref) * vec
        return np.linalg.solve(a, b)

    for _ in range(max(1, int(iterations))):
        for u, obs in by_user.items():
            X[u] = _solve_entity(Y, obs)
        for i, obs in by_item.items():
            Y[i] = _solve_entity(X, obs)

    return X.astype(np.float32), Y.astype(np.float32)


def fit_legacy_positive_als(
    *,
    n_users: int,
    n_items: int,
    observations: list[tuple[int, int, float, float]],
    factors: int = 32,
    iterations: int = 15,
) -> tuple[np.ndarray, np.ndarray]:
    """Positives-only implicit ALS (pre-Step-92 baseline)."""
    acc: dict[tuple[int, int], float] = defaultdict(float)
    for u, i, conf, pref in observations:
        if pref <= 0:
            continue
        acc[(u, i)] += float(conf)
    if not acc:
        raise ValueError("Need at least one positive observation for legacy ALS")
    row_idx, col_idx, data = zip(*((u, i, c) for (u, i), c in acc.items()), strict=True)
    user_item = sp.coo_matrix(
        (list(data), (list(row_idx), list(col_idx))),
        shape=(n_users, n_items),
    ).tocsr()
    model = AlternatingLeastSquares(
        factors=factors,
        iterations=iterations,
        random_state=42,
    )
    model.fit(user_item)
    return (
        np.asarray(model.user_factors, dtype=np.float32),
        np.asarray(model.item_factors, dtype=np.float32),
    )


def train_cf_als(
    *,
    factors: int = 32,
    iterations: int = 15,
    force: bool = False,
    shuffle_interactions: bool = False,
    holdout_days: int | None = None,
    use_negatives: bool | None = None,
) -> dict:
    """Train confidence-weighted ALS and promote only when holdout metrics improve.

    Step 91: gated promotion. Step 92: REJECT / VIEW-only enter as hard / weak
    negatives (preference 0 with elevated confidence) when ``CF_USE_NEGATIVES``.
    """
    rows = _training_rows(shuffle_interactions=shuffle_interactions)
    if len(rows) < 5:
        raise ValueError(
            f"Need at least 5 interactions to train CF (have {len(rows)}). "
            "Run seed_interactions or use the app to generate views."
        )

    signals = classify_pair_signals(rows)
    patient_ids = sorted({pid for pid, _ in signals})
    caregiver_ids = sorted({cid for _, cid in signals})
    if not patient_ids or not caregiver_ids:
        raise ValueError("No patient/caregiver pairs available for CF training.")

    patient_to_idx = {pid: i for i, pid in enumerate(patient_ids)}
    caregiver_to_idx = {cid: i for i, cid in enumerate(caregiver_ids)}

    negatives_on = (
        bool(getattr(settings, "CF_USE_NEGATIVES", True))
        if use_negatives is None
        else bool(use_negatives)
    )
    positive_alpha = float(getattr(settings, "CF_POSITIVE_ALPHA", 40.0))
    reject_alpha = float(getattr(settings, "CF_REJECT_ALPHA", 80.0))
    weak_neg_alpha = float(getattr(settings, "CF_WEAK_NEG_ALPHA", 5.0))

    observations, counts = build_confidence_observations(
        signals,
        patient_to_idx=patient_to_idx,
        caregiver_to_idx=caregiver_to_idx,
        use_negatives=negatives_on,
        positive_alpha=positive_alpha,
        reject_alpha=reject_alpha,
        weak_neg_alpha=weak_neg_alpha,
    )
    if not observations:
        raise ValueError(
            "Need at least one CF observation after classifying interactions "
            f"(raw_rows={len(rows)})."
        )
    if counts["positive"] == 0 and negatives_on:
        raise ValueError(
            "Need at least one positive pair to train CF with negatives "
            f"(counts={counts})."
        )

    objective = "confidence_wals_negatives" if negatives_on else "legacy_positive_als"
    if negatives_on:
        user_factors, item_factors = fit_confidence_weighted_als(
            n_users=len(patient_ids),
            n_items=len(caregiver_ids),
            observations=observations,
            factors=factors,
            iterations=iterations,
        )
    else:
        user_factors, item_factors = fit_legacy_positive_als(
            n_users=len(patient_ids),
            n_items=len(caregiver_ids),
            observations=observations,
            factors=factors,
            iterations=iterations,
        )

    version = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    meta = _write_artifact(
        version=version,
        patient_ids=patient_ids,
        caregiver_ids=caregiver_ids,
        user_factors=user_factors,
        item_factors=item_factors,
        n_interactions=len(rows),
        factors=factors,
        activate=False,
        extra_metrics={
            "objective": objective,
            "use_negatives": negatives_on,
            "n_positive_pairs": counts["positive"],
            "n_hard_negatives": counts["hard_negative"],
            "n_weak_negatives": counts["weak_negative"],
            "positive_alpha": positive_alpha,
            "reject_alpha": reject_alpha,
            "weak_neg_alpha": weak_neg_alpha,
        },
    )
    decision = decide_and_maybe_promote(
        version=version,
        version_dir=Path(meta["artifact_path"]),
        force=force,
        holdout_days=holdout_days,
    )
    meta.update(decision)
    meta["objective"] = objective
    meta["signal_counts"] = counts
    return meta


def _metric_from_report(report, metric: str) -> float:
    key = (metric or "ndcg_at_5").strip()
    mapping = {
        "ndcg_at_5": report.ndcg_at_5,
        "ndcg@5": report.ndcg_at_5,
        "map": report.map_score,
        "map_score": report.map_score,
        "recall_at_10": report.recall_at_10,
        "recall@10": report.recall_at_10,
        "precision_at_5": report.precision_at_5,
        "precision@5": report.precision_at_5,
    }
    if key not in mapping:
        raise ValueError(f"Unknown CF_PROMOTE_METRIC={metric!r}")
    return float(mapping[key])


def report_to_metrics(report) -> dict[str, Any]:
    return {
        "ndcg_at_5": report.ndcg_at_5,
        "map": report.map_score,
        "recall_at_10": report.recall_at_10,
        "precision_at_5": report.precision_at_5,
        "catalogue_coverage": report.catalogue_coverage,
        "exposure_gini": report.exposure_gini,
        "n_runs": report.n_runs,
        "n_labelled": report.n_labelled,
        "holdout_start": report.holdout_start.isoformat(),
        "holdout_end": report.holdout_end.isoformat(),
    }


def should_promote(
    *,
    candidate_score: float,
    incumbent_score: float,
    margin: float,
) -> bool:
    """True when candidate beats incumbent by at least ``margin`` on the primary metric."""
    return float(candidate_score) >= float(incumbent_score) + float(margin)


def decide_and_maybe_promote(
    *,
    version: str,
    version_dir: Path,
    force: bool = False,
    holdout_days: int | None = None,
) -> dict[str, Any]:
    """Compare candidate vs incumbent on holdout; promote or leave incumbent active."""
    from .cf_eval import evaluate_ranking

    gated = getattr(settings, "CF_GATED_PROMOTION", True)
    margin = float(getattr(settings, "CF_PROMOTE_MARGIN", 0.01))
    metric = str(getattr(settings, "CF_PROMOTE_METRIC", "ndcg_at_5"))
    days = int(holdout_days or getattr(settings, "CF_EVAL_HOLDOUT_DAYS", 14))

    candidate_model = load_cf_model_from_dir(version_dir)
    if candidate_model is None:
        raise ValueError(f"Candidate CF artifact missing under {version_dir}")

    incumbent_model = load_cf_model(force=True)
    incumbent_version = incumbent_model.version if isinstance(incumbent_model, AlsCFModel) else None

    # Cold start: no active pointer yet → always promote.
    if incumbent_model is None or not isinstance(incumbent_model, AlsCFModel):
        promote_cf_version(version, force=True, reason="cold_start")
        return {
            "promoted": True,
            "reason": "cold_start",
            "incumbent_version": None,
            "candidate_version": version,
            "metric": metric,
            "margin": margin,
        }

    if force or not gated:
        reason = "force" if force else "gated_disabled"
        cand_report = evaluate_ranking(days=days, cf_model=candidate_model)
        inc_report = evaluate_ranking(days=days, cf_model=incumbent_model)
        _record_eval_metrics(version, cand_report, role="candidate")
        _record_eval_metrics(incumbent_version or "", inc_report, role="incumbent")
        promote_cf_version(version, force=True, reason=reason)
        return {
            "promoted": True,
            "reason": reason,
            "incumbent_version": incumbent_version,
            "candidate_version": version,
            "candidate_score": _metric_from_report(cand_report, metric),
            "incumbent_score": _metric_from_report(inc_report, metric),
            "metric": metric,
            "margin": margin,
            "candidate_metrics": report_to_metrics(cand_report),
            "incumbent_metrics": report_to_metrics(inc_report),
        }

    cand_report = evaluate_ranking(days=days, cf_model=candidate_model)
    inc_report = evaluate_ranking(days=days, cf_model=incumbent_model)
    cand_score = _metric_from_report(cand_report, metric)
    inc_score = _metric_from_report(inc_report, metric)
    _record_eval_metrics(version, cand_report, role="candidate")
    _record_eval_metrics(incumbent_version or "", inc_report, role="incumbent")

    # No labelled holdout → keep incumbent (cannot prove improvement).
    if cand_report.n_labelled == 0 and inc_report.n_labelled == 0:
        logger.info(
            "cf_promote.rejected",
            extra={
                "reason": "no_holdout_labels",
                "candidate_version": version,
                "incumbent_version": incumbent_version,
            },
        )
        return {
            "promoted": False,
            "reason": "no_holdout_labels",
            "incumbent_version": incumbent_version,
            "candidate_version": version,
            "candidate_score": cand_score,
            "incumbent_score": inc_score,
            "metric": metric,
            "margin": margin,
            "candidate_metrics": report_to_metrics(cand_report),
            "incumbent_metrics": report_to_metrics(inc_report),
        }

    win = should_promote(candidate_score=cand_score, incumbent_score=inc_score, margin=margin)
    if win:
        promote_cf_version(version, force=True, reason="holdout_win")
        logger.info(
            "cf_promote.accepted",
            extra={
                "candidate_version": version,
                "incumbent_version": incumbent_version,
                "candidate_score": cand_score,
                "incumbent_score": inc_score,
                "metric": metric,
                "margin": margin,
            },
        )
        return {
            "promoted": True,
            "reason": "holdout_win",
            "incumbent_version": incumbent_version,
            "candidate_version": version,
            "candidate_score": cand_score,
            "incumbent_score": inc_score,
            "metric": metric,
            "margin": margin,
            "candidate_metrics": report_to_metrics(cand_report),
            "incumbent_metrics": report_to_metrics(inc_report),
        }

    logger.info(
        "cf_promote.rejected",
        extra={
            "reason": "holdout_loss",
            "candidate_version": version,
            "incumbent_version": incumbent_version,
            "candidate_score": cand_score,
            "incumbent_score": inc_score,
            "metric": metric,
            "margin": margin,
        },
    )
    return {
        "promoted": False,
        "reason": "holdout_loss",
        "incumbent_version": incumbent_version,
        "candidate_version": version,
        "candidate_score": cand_score,
        "incumbent_score": inc_score,
        "metric": metric,
        "margin": margin,
        "candidate_metrics": report_to_metrics(cand_report),
        "incumbent_metrics": report_to_metrics(inc_report),
    }


def _record_eval_metrics(version: str, report, *, role: str) -> None:
    if not version:
        return
    row = ModelVersion.objects.filter(kind=ModelKind.CF, version=version).first()
    if row is None:
        return
    metrics = dict(row.metrics or {})
    metrics["holdout"] = report_to_metrics(report)
    metrics["holdout_role"] = role
    row.metrics = metrics
    row.save(update_fields=["metrics"])


def promote_cf_version(version: str, *, force: bool = False, reason: str = "manual") -> dict:
    """Activate a trained CF version (updates pointer + ModelVersion).

    When ``force`` is false, re-runs the holdout gate against the incumbent.
    """
    ver = (version or "").strip()
    if not ver:
        raise ValueError("version is required")

    version_dir = cf_artifact_dir() / f"v{ver}"
    if not version_dir.exists():
        raise ValueError(f"CF artifact directory not found: {version_dir}")

    if not force:
        return decide_and_maybe_promote(version=ver, version_dir=version_dir, force=False)

    set_current_cf_pointer(version=ver, dir_name=version_dir.name)
    row = None
    try:
        from .model_registry import register_model_version

        meta_path = version_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        existing = ModelVersion.objects.filter(kind=ModelKind.CF, version=ver).first()
        preserved = dict(existing.metrics) if existing and existing.metrics else {}
        preserved["promotion_reason"] = reason
        for key in ("n_patients", "n_caregivers", "factors", "n_interactions"):
            if key in meta and key not in preserved:
                preserved[key] = meta[key]

        row = register_model_version(
            kind=ModelKind.CF,
            version=ver,
            rows_trained_on=int(meta.get("n_interactions") or preserved.get("n_interactions") or 0),
            metrics=preserved,
            artifact_path=str(version_dir),
            trained_at=meta.get("trained_at"),
            activate=True,
        )
    except Exception:
        logger.exception("CF promote registry update failed for %s", ver)

    reset_cf_cache()
    logger.info(
        "cf_promote.activated",
        extra={"candidate_version": ver, "reason": reason},
    )
    return {
        "promoted": True,
        "reason": reason,
        "candidate_version": ver,
        "model_version_id": getattr(row, "pk", None),
    }


def _write_artifact(
    *,
    version: str,
    patient_ids: list[int],
    caregiver_ids: list[int],
    user_factors: np.ndarray,
    item_factors: np.ndarray,
    n_interactions: int,
    factors: int,
    activate: bool = False,
    extra_metrics: dict | None = None,
) -> dict:
    root = cf_artifact_dir()
    version_dir = root / f"v{version}"
    version_dir.mkdir(parents=True, exist_ok=True)

    np.savez(
        version_dir / "factors.npz",
        user_factors=user_factors,
        item_factors=item_factors,
    )
    metrics = {
        "n_patients": len(patient_ids),
        "n_caregivers": len(caregiver_ids),
        "factors": factors,
        "n_interactions": n_interactions,
        **(extra_metrics or {}),
    }
    meta = {
        "version": version,
        "trained_at": datetime.now(UTC).isoformat(),
        "patient_ids": patient_ids,
        "caregiver_ids": caregiver_ids,
        "n_interactions": n_interactions,
        "n_patients": len(patient_ids),
        "n_caregivers": len(caregiver_ids),
        "factors": factors,
        "artifact_path": str(version_dir),
        "objective": (extra_metrics or {}).get("objective", "legacy_positive_als"),
    }
    (version_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    if activate:
        set_current_cf_pointer(version=version, dir_name=version_dir.name)

    try:
        from .model_registry import register_model_version

        register_model_version(
            kind=ModelKind.CF,
            version=version,
            rows_trained_on=n_interactions,
            metrics=metrics,
            artifact_path=str(version_dir),
            trained_at=meta["trained_at"],
            activate=activate,
        )
    except Exception:
        # Training must still succeed if the registry write fails (e.g. mid-migration).
        logger.exception("CF ModelVersion register failed")
    return meta


def patient_cf_scores(patient_id: int, *, top_k: int = 10) -> list[dict]:
    """Return top caregiver CF scores for one patient (post-training smoke test)."""
    model = load_cf_model(force=True)
    if model is None:
        raise ValueError("No CF artifact found — run train_cf first.")

    if patient_id not in model._patient_idx:
        return []

    caregiver_ids = model.caregiver_ids
    scores = model.predict(patient_id, caregiver_ids)
    ranked = sorted(
        zip(caregiver_ids, scores.tolist(), strict=True),
        key=lambda row: row[1],
        reverse=True,
    )[:top_k]
    return [
        {"caregiver_id": cid, "cf_score": round(score, 6)} for cid, score in ranked
    ]
