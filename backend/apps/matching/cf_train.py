"""Offline ALS training for patient ↔ caregiver CF (Steps 21 / 91)."""

from __future__ import annotations

import json
import logging
import random
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
from .models import Interaction, ModelKind, ModelVersion

logger = logging.getLogger(__name__)


def train_cf_als(
    *,
    factors: int = 32,
    iterations: int = 15,
    force: bool = False,
    shuffle_interactions: bool = False,
    holdout_days: int | None = None,
) -> dict:
    """Train implicit ALS and promote only when holdout metrics beat the incumbent.

    Step 91: writes a versioned artifact always; updates ``current.json`` / active
    ``ModelVersion`` only when the candidate wins (or ``force=True`` / cold start).
    """
    rows = list(
        Interaction.objects.values_list("patient_id", "caregiver_id", "weight")
    )
    if len(rows) < 5:
        raise ValueError(
            f"Need at least 5 interactions to train CF (have {len(rows)}). "
            "Run seed_interactions or use the app to generate views."
        )

    if shuffle_interactions:
        # Deliberately break patient↔caregiver pairing (acceptance / regression).
        caregivers = [r[1] for r in rows]
        rng = random.Random(0)
        rng.shuffle(caregivers)
        rows = [(r[0], caregivers[i], r[2]) for i, r in enumerate(rows)]

    patient_ids = sorted({r[0] for r in rows})
    caregiver_ids = sorted({r[1] for r in rows})
    patient_to_idx = {pid: i for i, pid in enumerate(patient_ids)}
    caregiver_to_idx = {cid: i for i, cid in enumerate(caregiver_ids)}

    acc: dict[tuple[int, int], float] = defaultdict(float)
    for patient_id, caregiver_id, weight in rows:
        value = float(weight)
        if value <= 0:
            # REJECT is stored negative for Step 92; implicit ALS needs non-negative confidence.
            continue
        key = (patient_to_idx[patient_id], caregiver_to_idx[caregiver_id])
        acc[key] += value
    acc = {k: v for k, v in acc.items() if v > 0}
    if not acc:
        raise ValueError(
            "Need at least one non-negative interaction to train CF "
            f"(have {len(rows)} row(s), all skipped)."
        )

    row_idx, col_idx, data = zip(*((k[0], k[1], v) for k, v in acc.items()), strict=True)
    user_item = sp.coo_matrix(
        (list(data), (list(row_idx), list(col_idx))),
        shape=(len(patient_ids), len(caregiver_ids)),
    ).tocsr()

    model = AlternatingLeastSquares(
        factors=factors,
        iterations=iterations,
        random_state=42,
    )
    model.fit(user_item)

    version = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    meta = _write_artifact(
        version=version,
        patient_ids=patient_ids,
        caregiver_ids=caregiver_ids,
        user_factors=model.user_factors,
        item_factors=model.item_factors,
        n_interactions=len(rows),
        factors=factors,
        activate=False,
    )
    decision = decide_and_maybe_promote(
        version=version,
        version_dir=Path(meta["artifact_path"]),
        force=force,
        holdout_days=holdout_days,
    )
    meta.update(decision)
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
) -> dict:
    root = cf_artifact_dir()
    version_dir = root / f"v{version}"
    version_dir.mkdir(parents=True, exist_ok=True)

    np.savez(
        version_dir / "factors.npz",
        user_factors=user_factors,
        item_factors=item_factors,
    )
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
            metrics={
                "n_patients": len(patient_ids),
                "n_caregivers": len(caregiver_ids),
                "factors": factors,
                "n_interactions": n_interactions,
            },
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
