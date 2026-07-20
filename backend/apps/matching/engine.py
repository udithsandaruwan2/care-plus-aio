"""VEHMF matching engine — CBF + CF + Geo + Trust fusion + XAI (Step 19).

Lean profile: in-process module. CF is a neutral stub until Step 21 trains ALS.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point

from .ahp import get_ahp_weights, normalize_weights
from .embeddings import get_embedder, intent_to_text
from .faiss_index import CaregiverIndex, load_index
from .models import CaregiverProfile

_XAI = {
    0: "strong medical/skill match",
    1: "highly rated by similar patients",
    2: "very close / short travel time",
    3: "high trust & completion record",
}

# Soft distance scale: ~50 km → score ≈ 0.5 (geography metres).
_GEO_HALF_LIFE_M = 50_000.0


@dataclass(frozen=True)
class RankedMatch:
    caregiver_id: int
    score: float
    cbf: float
    cf: float
    geo: float
    trust: float
    explanation: str
    distance_m: float | None = None


@dataclass(frozen=True)
class MatchOutput:
    results: list[RankedMatch]
    weights: tuple[float, float, float, float]
    query: str
    emergency: bool


def _normalize(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if x.size == 0:
        return x
    rng = float(np.ptp(x))
    if rng <= 0:
        return np.zeros_like(x)
    return (x - x.min()) / rng


class StubCFModel:
    """Neutral collaborative scores until offline ALS lands (Step 21)."""

    def predict(self, patient_id: int | None, caregiver_ids: Sequence[int]) -> np.ndarray:
        return np.full(len(caregiver_ids), 0.5, dtype=np.float32)


class VEHMFEngine:
    def __init__(
        self,
        ahp_weights: tuple[float, ...] | None = None,
        faiss_index: CaregiverIndex | None = None,
        cf_model: StubCFModel | None = None,
    ):
        self.W = np.asarray(
            ahp_weights if ahp_weights is not None else get_ahp_weights(),
            dtype=np.float32,
        )
        self.index = faiss_index if faiss_index is not None else load_index()
        self.cf_model = cf_model or StubCFModel()

    def predict(
        self,
        *,
        query_text: str,
        patient_id: int | None = None,
        origin: Point | None = None,
        top_k: int = 10,
        candidate_pool: int = 100,
        weights: Sequence[float] | None = None,
        emergency: bool = False,
    ) -> MatchOutput:
        if self.index.size == 0:
            return MatchOutput(
                results=[],
                weights=tuple(float(w) for w in self.W),
                query=query_text,
                emergency=emergency,
            )

        W = (
            np.asarray(normalize_weights(list(weights)), dtype=np.float32)
            if weights is not None
            else np.asarray(
                get_ahp_weights(emergency=True) if emergency else self.W,
                dtype=np.float32,
            )
        )

        # 1. CBF — FAISS inner product on L2-normalized vectors.
        qvec = get_embedder().embed([query_text])[0]
        pool = min(candidate_pool, self.index.size)
        cbf_hits = self.index.search(qvec, k=pool)
        if not cbf_hits:
            return MatchOutput(
                results=[],
                weights=tuple(float(w) for w in W),
                query=query_text,
                emergency=emergency,
            )

        caregiver_ids = [cid for cid, _ in cbf_hits]
        cbf_raw = np.array([score for _, score in cbf_hits], dtype=np.float32)

        # Soft presence (Step 20e): unavailable caregivers stay in the FAISS index
        # but are hidden from match top-N (browse can still show them via ?available=0).
        profiles = {
            p.id: p
            for p in CaregiverProfile.objects.filter(
                id__in=caregiver_ids, is_active=True, is_available=True
            )
        }
        # Keep FAISS order but drop missing/inactive/unavailable.
        ordered_ids = [cid for cid in caregiver_ids if cid in profiles]
        if not ordered_ids:
            return MatchOutput(
                results=[],
                weights=tuple(float(w) for w in W),
                query=query_text,
                emergency=emergency,
            )

        id_to_cbf = {cid: s for cid, s in cbf_hits}
        cbf_raw = np.array([id_to_cbf[cid] for cid in ordered_ids], dtype=np.float32)
        cbf = _normalize(cbf_raw)

        # 2. CF — stub until Step 21.
        cf = _normalize(self.cf_model.predict(patient_id, ordered_ids))

        # 3. Geo — distance → 0..1 (closer = higher).
        geo_raw, distances = self._geo_scores(origin, ordered_ids, profiles)
        geo = _normalize(geo_raw)

        # 4. Trust — profile trust_score (already 0..1; still normalize across pool).
        trust_raw = np.array(
            [float(profiles[cid].trust_score) for cid in ordered_ids], dtype=np.float32
        )
        trust = _normalize(trust_raw)

        # 5. Fusion.
        score_matrix = np.column_stack((cbf, cf, geo, trust))
        final = score_matrix @ W

        # 6. Rank + XAI for each returned row (explanation uses that row's dominant factor).
        order = np.argsort(-final)[:top_k]
        results: list[RankedMatch] = []
        for idx in order:
            i = int(idx)
            cid = ordered_ids[i]
            row = score_matrix[i]
            contributor = int(np.argmax(row * W))
            results.append(
                RankedMatch(
                    caregiver_id=cid,
                    score=float(final[i]),
                    cbf=float(row[0]),
                    cf=float(row[1]),
                    geo=float(row[2]),
                    trust=float(row[3]),
                    explanation=f"Matched because: {_XAI[contributor]}.",
                    distance_m=distances.get(cid),
                )
            )

        return MatchOutput(
            results=results,
            weights=tuple(float(w) for w in W),
            query=query_text,
            emergency=emergency,
        )

    def _geo_scores(
        self,
        origin: Point | None,
        caregiver_ids: list[int],
        profiles: dict[int, CaregiverProfile],
    ) -> tuple[np.ndarray, dict[int, float | None]]:
        distances: dict[int, float | None] = {cid: None for cid in caregiver_ids}
        if origin is None:
            return np.full(len(caregiver_ids), 0.5, dtype=np.float32), distances

        # Annotate distance in metres via PostGIS geography.
        qs = (
            CaregiverProfile.objects.filter(id__in=caregiver_ids)
            .annotate(dist=Distance("location", origin))
            .values_list("id", "dist")
        )
        metres = {cid: float(d.m) if d is not None else None for cid, d in qs}
        scores = []
        for cid in caregiver_ids:
            m = metres.get(cid)
            distances[cid] = m
            if m is None:
                scores.append(0.5)
            else:
                # Exponential decay with distance.
                scores.append(float(np.exp(-m / _GEO_HALF_LIFE_M)))
        return np.asarray(scores, dtype=np.float32), distances


def run_match(
    *,
    condition: str = "",
    language: str = "",
    care_level: str = "",
    query: str = "",
    patient_id: int | None = None,
    longitude: float | None = None,
    latitude: float | None = None,
    top_k: int = 10,
    emergency: bool = False,
    engine: VEHMFEngine | None = None,
) -> MatchOutput:
    """Convenience wrapper used by the API layer."""
    text = intent_to_text(
        condition=condition, language=language, care_level=care_level, extra=query
    )
    origin = None
    if longitude is not None and latitude is not None:
        origin = Point(float(longitude), float(latitude), srid=4326)
    eng = engine or VEHMFEngine()
    return eng.predict(
        query_text=text or query or "care",
        patient_id=patient_id,
        origin=origin,
        top_k=top_k,
        emergency=emergency,
    )
