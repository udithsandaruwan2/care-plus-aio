"""Collaborative filtering model loader (implicit ALS — Step 21)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
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

    def predict(self, patient_id: int | None, caregiver_ids: Sequence[int]) -> np.ndarray:
        if patient_id is None or patient_id not in self._patient_idx:
            return np.full(len(caregiver_ids), 0.5, dtype=np.float32)
        u = self.user_factors[self._patient_idx[patient_id]]
        raw = np.array(
            [
                float(np.dot(u, self.item_factors[self._caregiver_idx[cid]]))
                if cid in self._caregiver_idx
                else 0.0
                for cid in caregiver_ids
            ],
            dtype=np.float32,
        )
        return _normalize_scores(raw)

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
    meta_path = version_dir / "meta.json"
    factors_path = version_dir / "factors.npz"
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
    _CACHE = model
    return model


def get_cf_model() -> CFModel:
    """Return the active CF model (ALS artifact) or a neutral stub."""
    if not getattr(settings, "CF_ENABLED", True):
        return StubCFModel()
    return load_cf_model() or StubCFModel()


def cf_model_info(model: CFModel) -> dict:
    """Metadata for API responses and fusion diagnostics."""
    if isinstance(model, AlsCFModel):
        return {"enabled": True, "backend": "als", "version": model.version}
    if isinstance(model, StubCFModel):
        return {"enabled": False, "backend": "stub", "version": None}
    return {"enabled": is_cf_active(model), "backend": "custom", "version": getattr(model, "version", None)}


def is_cf_active(model: CFModel) -> bool:
    """True when CF contributes to fusion (trained ALS or an injected model)."""
    if not getattr(settings, "CF_ENABLED", True):
        return False
    return not isinstance(model, StubCFModel)
