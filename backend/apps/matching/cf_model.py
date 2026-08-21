"""Collaborative filtering model loader (implicit ALS — Step 21 / 99)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np
from django.conf import settings


class CFModel(Protocol):
    def predict(self, patient_id: int | None, caregiver_ids: Sequence[int]) -> np.ndarray: ...


@dataclass(frozen=True)
class StubCFModel:
    """Neutral collaborative scores when CF is disabled or not yet trained."""

    def predict(self, patient_id: int | None, caregiver_ids: Sequence[int]) -> np.ndarray:
        return np.full(len(caregiver_ids), 0.5, dtype=np.float32)


def cf_artifact_dir() -> Path:
    raw = getattr(settings, "CF_ARTIFACT_DIR", "")
    if raw:
        path = Path(raw)
    else:
        faiss_raw = getattr(settings, "FAISS_ARTIFACT_DIR", "")
        if faiss_raw:
            path = Path(faiss_raw) / "cf"
        else:
            path = Path(settings.BASE_DIR).parent / "ml" / "artifacts" / "cf"
            if not path.parent.parent.exists():
                path = Path(settings.BASE_DIR) / "var" / "cf"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalize_scores(scores: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=np.float32)
    if scores.size == 0:
        return scores
    rng = float(np.ptp(scores))
    if rng <= 0:
        return np.full_like(scores, 0.5)
    return (scores - scores.min()) / rng


@dataclass(frozen=True)
class AlsCFModel:
    """ALS factor model loaded from a versioned artifact directory."""

    version: str
    patient_ids: list[int]
    caregiver_ids: list[int]
    user_factors: np.ndarray
    item_factors: np.ndarray
    # Step 99 — cluster-mean item factors for caregivers absent from ALS training.
    cold_start_factors: Mapping[int, np.ndarray] = field(default_factory=dict)

    def with_cold_start(self, factors: Mapping[int, np.ndarray]) -> AlsCFModel:
        return AlsCFModel(
            version=self.version,
            patient_ids=self.patient_ids,
            caregiver_ids=self.caregiver_ids,
            user_factors=self.user_factors,
            item_factors=self.item_factors,
            cold_start_factors=dict(factors),
        )

    def _item_vector(self, cid: int) -> np.ndarray | None:
        idx = self._caregiver_idx.get(cid)
        if idx is not None:
            return self.item_factors[idx]
        vec = self.cold_start_factors.get(cid)
        if vec is not None:
            return np.asarray(vec, dtype=np.float32)
        return None

    def predict(self, patient_id: int | None, caregiver_ids: Sequence[int]) -> np.ndarray:
        if patient_id is None or patient_id not in self._patient_idx:
            return np.full(len(caregiver_ids), 0.5, dtype=np.float32)
        u = self.user_factors[self._patient_idx[patient_id]]
        global_mean = (
            self.item_factors.mean(axis=0).astype(np.float32)
            if self.item_factors.size
            else None
        )
        raw_list: list[float] = []
        for cid in caregiver_ids:
            vec = self._item_vector(int(cid))
            if vec is None and global_mean is not None and self.cold_start_factors:
                vec = global_mean
            if vec is None:
                raw_list.append(0.0)
            else:
                raw_list.append(float(np.dot(u, vec)))
        return _normalize_scores(np.asarray(raw_list, dtype=np.float32))

    def raw_scores(self, patient_id: int, caregiver_ids: Sequence[int]) -> np.ndarray:
        """Unnormalized dots — used by tests to assert cold-start ≠ 0."""
        if patient_id not in self._patient_idx:
            return np.zeros(len(caregiver_ids), dtype=np.float32)
        u = self.user_factors[self._patient_idx[patient_id]]
        out = []
        for cid in caregiver_ids:
            vec = self._item_vector(int(cid))
            out.append(0.0 if vec is None else float(np.dot(u, vec)))
        return np.asarray(out, dtype=np.float32)

    @property
    def _patient_idx(self) -> dict[int, int]:
        return {pid: i for i, pid in enumerate(self.patient_ids)}

    @property
    def _caregiver_idx(self) -> dict[int, int]:
        return {cid: i for i, cid in enumerate(self.caregiver_ids)}


_CACHE: AlsCFModel | None = None


def reset_cf_cache() -> None:
    global _CACHE
    _CACHE = None


def load_cf_model(*, force: bool = False) -> AlsCFModel | None:
    """Load the latest CF artifact, or ``None`` when none has been trained yet."""
    global _CACHE
    if _CACHE is not None and not force:
        return _CACHE

    pointer = cf_artifact_dir() / "current.json"
    if not pointer.exists():
        return None

    doc = json.loads(pointer.read_text(encoding="utf-8"))
    version_dir = cf_artifact_dir() / doc["dir"]
    model = load_cf_model_from_dir(version_dir)
    if model is None:
        return None
    _CACHE = model
    return model


def load_cf_model_from_dir(version_dir: Path | str) -> AlsCFModel | None:
    """Load an ALS artifact from a version directory (does not touch the cache)."""
    path = Path(version_dir)
    meta_path = path / "meta.json"
    factors_path = path / "factors.npz"
    if not meta_path.exists() or not factors_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    factors = np.load(factors_path)
    model = AlsCFModel(
        version=meta["version"],
        patient_ids=list(meta["patient_ids"]),
        caregiver_ids=list(meta["caregiver_ids"]),
        user_factors=np.asarray(factors["user_factors"], dtype=np.float32),
        item_factors=np.asarray(factors["item_factors"], dtype=np.float32),
    )
    try:
        from apps.matching.clustering import load_cold_start_vectors

        cold = load_cold_start_vectors()
        if cold:
            model = model.with_cold_start(cold)
    except Exception:
        pass
    return model


def set_current_cf_pointer(*, version: str, dir_name: str) -> None:
    """Point ``current.json`` at a trained version directory."""
    root = cf_artifact_dir()
    (root / "current.json").write_text(
        json.dumps({"version": version, "dir": dir_name}, indent=2),
        encoding="utf-8",
    )
    reset_cf_cache()


def get_cf_model() -> CFModel:
    """Return the active CF model (ALS artifact) or a neutral stub."""
    if not getattr(settings, "CF_ENABLED", True):
        return StubCFModel()
    return load_cf_model() or StubCFModel()


def cf_model_info(model: CFModel) -> dict:
    """Metadata for API responses and fusion diagnostics."""
    if isinstance(model, AlsCFModel):
        return {
            "enabled": True,
            "backend": "als",
            "version": model.version,
            "cold_start_seeded": len(model.cold_start_factors),
        }
    if isinstance(model, StubCFModel):
        return {"enabled": False, "backend": "stub", "version": None}
    return {
        "enabled": is_cf_active(model),
        "backend": "custom",
        "version": getattr(model, "version", None),
    }


def is_cf_active(model: CFModel) -> bool:
    """True when CF contributes to fusion (trained ALS or an injected model)."""
    if not getattr(settings, "CF_ENABLED", True):
        return False
    return not isinstance(model, StubCFModel)
