"""Offline ALS training for patient ↔ caregiver CF (Step 21)."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from implicit.als import AlternatingLeastSquares

from .cf_model import cf_artifact_dir, reset_cf_cache
from .models import Interaction


def train_cf_als(*, factors: int = 32, iterations: int = 15) -> dict:
    """Train implicit ALS on ``Interaction`` rows and write a versioned artifact."""
    rows = list(
        Interaction.objects.values_list("patient_id", "caregiver_id", "weight")
    )
    if len(rows) < 5:
        raise ValueError(
            f"Need at least 5 interactions to train CF (have {len(rows)}). "
            "Run seed_interactions or use the app to generate views."
        )

    patient_ids = sorted({r[0] for r in rows})
    caregiver_ids = sorted({r[1] for r in rows})
    patient_to_idx = {pid: i for i, pid in enumerate(patient_ids)}
    caregiver_to_idx = {cid: i for i, cid in enumerate(caregiver_ids)}

    acc: dict[tuple[int, int], float] = defaultdict(float)
    for patient_id, caregiver_id, weight in rows:
        key = (patient_to_idx[patient_id], caregiver_to_idx[caregiver_id])
        acc[key] += float(weight)

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
    out_dir = _write_artifact(
        version=version,
        patient_ids=patient_ids,
        caregiver_ids=caregiver_ids,
        user_factors=model.user_factors,
        item_factors=model.item_factors,
        n_interactions=len(rows),
        factors=factors,
    )
    reset_cf_cache()
    return out_dir


def _write_artifact(
    *,
    version: str,
    patient_ids: list[int],
    caregiver_ids: list[int],
    user_factors: np.ndarray,
    item_factors: np.ndarray,
    n_interactions: int,
    factors: int,
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
    }
    (version_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (root / "current.json").write_text(
        json.dumps({"version": version, "dir": version_dir.name}, indent=2),
        encoding="utf-8",
    )
    return meta


def patient_cf_scores(patient_id: int, *, top_k: int = 10) -> list[dict]:
    """Return top caregiver CF scores for one patient (post-training smoke test)."""
    from .cf_model import load_cf_model

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
