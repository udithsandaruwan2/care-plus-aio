"""FAISS IndexFlatIP store for caregiver embeddings (Step 17).

Vectors must be L2-normalized so inner product == cosine similarity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np
from django.conf import settings

from .embeddings import get_embedder, profile_to_text
from .models import EMBEDDING_DIM, CaregiverProfile


def artifact_dir() -> Path:
    raw = getattr(settings, "FAISS_ARTIFACT_DIR", "")
    if raw:
        path = Path(raw)
    else:
        # Prefer repo ``ml/artifacts`` when mounted; else ``backend/var/faiss``.
        path = Path(settings.BASE_DIR).parent / "ml" / "artifacts"
        if not path.parent.exists():
            path = Path(settings.BASE_DIR) / "var" / "faiss"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class CaregiverIndex:
    """In-memory FAISS index + parallel caregiver id list."""

    index: faiss.IndexFlatIP
    caregiver_ids: list[int]
    backend: str

    @property
    def size(self) -> int:
        return len(self.caregiver_ids)

    def search(self, query_vec: np.ndarray, k: int = 10) -> list[tuple[int, float]]:
        """Return ``[(caregiver_id, score), …]`` sorted by descending IP."""
        if self.size == 0:
            return []
        q = np.asarray(query_vec, dtype=np.float32).reshape(1, -1)
        k = min(k, self.size)
        scores, idxs = self.index.search(q, k)
        out: list[tuple[int, float]] = []
        for score, idx in zip(scores[0], idxs[0], strict=True):
            if idx < 0:
                continue
            out.append((self.caregiver_ids[int(idx)], float(score)))
        return out


def build_index(*, persist: bool = True) -> CaregiverIndex:
    """Embed all active caregivers, write DB columns + optional FAISS artifacts."""
    embedder = get_embedder()
    backend = getattr(settings, "EMBEDDING_BACKEND", "hash")
    qs = (
        CaregiverProfile.objects.filter(is_active=True)
        .order_by("id")
        .only(
            "id",
            "display_name",
            "specialties",
            "certifications",
            "languages",
            "care_levels",
            "bio",
            "embedding",
        )
    )
    profiles = list(qs)
    texts = [profile_to_text(p) for p in profiles]
    if not texts:
        index = faiss.IndexFlatIP(EMBEDDING_DIM)
        built = CaregiverIndex(index=index, caregiver_ids=[], backend=backend)
        if persist:
            _persist(built, np.zeros((0, EMBEDDING_DIM), dtype=np.float32))
        return built

    mat = embedder.embed(texts)
    if mat.shape != (len(profiles), EMBEDDING_DIM):
        raise ValueError(f"embedding shape {mat.shape} unexpected")

    # Persist vectors on each profile row (for inspection / rebuild).
    for profile, row in zip(profiles, mat, strict=True):
        profile.embedding = row.tolist()
    CaregiverProfile.objects.bulk_update(profiles, ["embedding"], batch_size=100)

    index = faiss.IndexFlatIP(EMBEDDING_DIM)
    index.add(mat)
    ids = [p.id for p in profiles]
    built = CaregiverIndex(index=index, caregiver_ids=ids, backend=backend)
    if persist:
        _persist(built, mat)
    # Refresh process-local cache.
    _cache_set(built)
    return built


def _persist(built: CaregiverIndex, mat: np.ndarray) -> None:
    d = artifact_dir()
    faiss.write_index(built.index, str(d / "caregivers.faiss"))
    meta = {
        "caregiver_ids": built.caregiver_ids,
        "backend": built.backend,
        "dim": EMBEDDING_DIM,
        "count": built.size,
    }
    (d / "caregivers.ids.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    np.save(d / "caregivers.npy", mat)


def load_index() -> CaregiverIndex:
    """Load from artifacts if present, else rebuild from DB."""
    cached = _cache_get()
    if cached is not None:
        return cached
    d = artifact_dir()
    faiss_path = d / "caregivers.faiss"
    meta_path = d / "caregivers.ids.json"
    if faiss_path.exists() and meta_path.exists():
        index = faiss.read_index(str(faiss_path))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        built = CaregiverIndex(
            index=index,
            caregiver_ids=list(meta["caregiver_ids"]),
            backend=meta.get("backend", "hash"),
        )
        _cache_set(built)
        return built
    return build_index(persist=True)


# Process-local singleton (Lean: in-process VEHMF).
_CACHE: CaregiverIndex | None = None


def _cache_get() -> CaregiverIndex | None:
    return _CACHE


def _cache_set(index: CaregiverIndex) -> None:
    global _CACHE
    _CACHE = index


def reset_cache() -> None:
    global _CACHE
    _CACHE = None
