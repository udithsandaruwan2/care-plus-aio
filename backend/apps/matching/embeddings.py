"""Text → L2-normalized embedding vectors for caregiver CBF (Step 17).

Backends
--------
``hash`` (default)
    Signed feature-hashing into ``EMBEDDING_DIM`` dims. Shared tokens boost
    inner product, so specialty/language queries rank the right caregivers
    without downloading a neural model. Deterministic and CI-friendly.

``e5``
    ``intfloat/multilingual-e5-base`` via sentence-transformers (optional).
    Enable with ``EMBEDDING_BACKEND=e5`` once the model wheel is installed.
    Falls back to ``hash`` if the package/model is unavailable.
"""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

import numpy as np
from django.conf import settings

from .models import EMBEDDING_DIM, CaregiverProfile

_TOKEN_RE = re.compile(r"[a-z0-9\u0d80-\u0dff\u0b80-\u0bff]+", re.I)


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return (N, dim) float32 L2-normalized row vectors."""
        ...


def profile_to_text(profile: CaregiverProfile) -> str:
    """Flatten a caregiver profile into the document we embed."""
    parts = [
        " ".join(profile.specialties or []),
        " ".join(profile.certifications or []),
        " ".join(profile.languages or []),
        " ".join(profile.care_levels or []),
        profile.bio or "",
        profile.display_name or "",
    ]
    return " ".join(p for p in parts if p).strip().lower()


def intent_to_text(
    *,
    condition: str = "",
    language: str = "",
    care_level: str = "",
    extra: str = "",
) -> str:
    """Build a query string from structured intent (+ optional free text)."""
    return " ".join(p for p in (condition, language, care_level, extra) if p).strip().lower()


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (mat / norms).astype(np.float32)


class HashEmbedder:
    """Deterministic signed hashing embedder (default lean backend)."""

    dim = EMBEDDING_DIM

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for tok in _TOKEN_RE.findall(text.lower()):
                digest = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
                idx = int.from_bytes(digest[:4], "little") % self.dim
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                out[i, idx] += sign
        return _l2_normalize(out)


class E5Embedder:
    """multilingual-e5-base wrapper. Lazy-loads sentence-transformers."""

    dim = EMBEDDING_DIM

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or getattr(
            settings, "EMBEDDING_MODEL", "intfloat/multilingual-e5-base"
        )
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(self.model_name)

    def embed(self, texts: list[str]) -> np.ndarray:
        self._load()
        # e5 models expect "query: …" / "passage: …"; use passage for both in MVP.
        prefixed = [f"passage: {t}" for t in texts]
        vecs = self._model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
        arr = np.asarray(vecs, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[1] != self.dim:
            raise ValueError(f"E5 dim {arr.shape[1]} != expected {self.dim}")
        return arr


def get_embedder() -> Embedder:
    backend = getattr(settings, "EMBEDDING_BACKEND", "hash").lower()
    if backend == "e5":
        try:
            return E5Embedder()
        except Exception:
            # Missing wheel / model download failure → stay online with hash.
            return HashEmbedder()
    return HashEmbedder()
