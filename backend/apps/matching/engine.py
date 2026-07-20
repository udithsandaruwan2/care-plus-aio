"""VEHMF matching engine — CBF + CF + Geo + Trust fusion + XAI (Step 19).

Step 22 loads trained ALS CF when available; ``CF_ENABLED=false`` zeroes β and
redistributes AHP weight across CBF/geo/trust.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point

from .ahp import get_ahp_weights, normalize_weights
from .cf_model import cf_model_info, get_cf_model, is_cf_active
from .embeddings import get_embedder, intent_to_text
from .faiss_index import CaregiverIndex, load_index
from .i18n import format_match_explanation
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
    cf_enabled: bool = False
    cf_version: str | None = None


def _effective_weights(W: np.ndarray, *, cf_active: bool) -> np.ndarray:
    """Zero β and redistribute when CF is inactive (Step 22 feature flag)."""
    W = np.asarray(W, dtype=np.float32)
    if cf_active:
        return W
    out = W.copy()
    cf_share = float(out[1])
    out[1] = 0.0
    mask = np.array([True, False, True, True])
    rest = out[mask]
    total = float(rest.sum())
    if total <= 0:
        return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    out[mask] = rest + cf_share * (rest / total)
    return out


def _normalize(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if x.size == 0:
        return x
    rng = float(np.ptp(x))
    if rng <= 0:
        return np.zeros_like(x)
    return (x - x.min()) / rng


class VEHMFEngine:
    def __init__(
        self,
        ahp_weights: tuple[float, ...] | None = None,
        faiss_index: CaregiverIndex | None = None,
        cf_model=None,
    ):
        self.W = np.asarray(
            ahp_weights if ahp_weights is not None else get_ahp_weights(),
            dtype=np.float32,
        )
        self.index = faiss_index if faiss_index is not None else load_index()
        self.cf_model = cf_model if cf_model is not None else get_cf_model()
        self._cf_info = cf_model_info(self.cf_model)

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
        max_distance_m: float | None = None,
        require_language: str = "",
        require_specialty: str = "",
        require_care_level: str = "",
        prefer_closer: bool = False,
    ) -> MatchOutput:
        if self.index.size == 0:
            return MatchOutput(
                results=[],
                weights=tuple(float(w) for w in self.W),
                query=query_text,
                emergency=emergency,
                cf_enabled=self._cf_info["enabled"],
                cf_version=self._cf_info["version"],
            )

        W = (
            np.asarray(normalize_weights(list(weights)), dtype=np.float32)
            if weights is not None
            else np.asarray(
                get_ahp_weights(emergency=True) if emergency else self.W,
                dtype=np.float32,
            )
        )
        # Soft refine: tilt fusion toward geography when user asks for closer.
        if prefer_closer and weights is None and not emergency:
            W = np.asarray(normalize_weights([0.25, 0.05, 0.55, 0.15]), dtype=np.float32)

        cf_active = is_cf_active(self.cf_model)
        W = _effective_weights(W, cf_active=cf_active)
        effective_weights = tuple(float(w) for w in W)

        # 1. CBF — FAISS inner product on L2-normalized vectors.
        qvec = get_embedder().embed([query_text])[0]
        pool = min(candidate_pool, self.index.size)
        cbf_hits = self.index.search(qvec, k=pool)
        if not cbf_hits:
            return MatchOutput(
                results=[],
                weights=effective_weights,
                query=query_text,
                emergency=emergency,
                cf_enabled=cf_active,
                cf_version=self._cf_info["version"],
            )

        caregiver_ids = [cid for cid, _ in cbf_hits]

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
                weights=effective_weights,
                query=query_text,
                emergency=emergency,
                cf_enabled=cf_active,
                cf_version=self._cf_info["version"],
            )

        id_to_cbf = {cid: s for cid, s in cbf_hits}
        cbf_raw = np.array([id_to_cbf[cid] for cid in ordered_ids], dtype=np.float32)
        cbf = _normalize(cbf_raw)

        # 2. CF — ALS when trained (Step 22), else neutral stub.
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

        # 6. Hard refine filters (Step 15i) then rank.
        lang_req = (require_language or "").strip()
        spec_req = (require_specialty or "").strip().lower()
        care_req = (require_care_level or "").strip().lower()

        eligible: list[int] = []
        for i, cid in enumerate(ordered_ids):
            p = profiles[cid]
            if lang_req and lang_req not in (p.languages or []):
                continue
            if care_req and care_req not in [c.lower() for c in (p.care_levels or [])]:
                continue
            if spec_req:
                specs = [s.lower() for s in (p.specialties or [])]
                if not any(spec_req in s or s in spec_req for s in specs):
                    continue
            dist = distances.get(cid)
            if max_distance_m is not None:
                if dist is None or dist > max_distance_m:
                    continue
            eligible.append(i)

        if not eligible:
            return MatchOutput(
                results=[],
                weights=effective_weights,
                query=query_text,
                emergency=emergency,
                cf_enabled=cf_active,
                cf_version=self._cf_info["version"],
            )

        eligible_arr = np.asarray(eligible, dtype=np.int64)
        order_local = np.argsort(-final[eligible_arr])[:top_k]
        results: list[RankedMatch] = []
        for loc in order_local:
            i = int(eligible_arr[int(loc)])
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
                    explanation=format_match_explanation(contributor, "en"),
                    distance_m=distances.get(cid),
                )
            )

        return MatchOutput(
            results=results,
            weights=effective_weights,
            query=query_text,
            emergency=emergency,
            cf_enabled=cf_active,
            cf_version=self._cf_info["version"],
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
    max_distance_km: float | None = None,
    specialty: str = "",
    prefer_closer: bool = False,
    hard_filter_language: bool = False,
    hard_filter_care_level: bool = False,
) -> MatchOutput:
    """Convenience wrapper used by the API layer.

    Soft CBF text always includes language/care_level. Hard filters (Step 15i
    refine) are opt-in so a normal match is not over-constrained.
    """
    extra = query
    if specialty:
        extra = f"{specialty} {query}".strip()
    text = intent_to_text(
        condition=condition or specialty,
        language=language,
        care_level=care_level,
        extra=extra,
    )
    origin = None
    if longitude is not None and latitude is not None:
        origin = Point(float(longitude), float(latitude), srid=4326)
    eng = engine or VEHMFEngine()
    max_m = None if max_distance_km is None else float(max_distance_km) * 1000.0
    return eng.predict(
        query_text=text or query or "care",
        patient_id=patient_id,
        origin=origin,
        top_k=top_k,
        emergency=emergency,
        max_distance_m=max_m,
        require_language=language if hard_filter_language else "",
        require_specialty=specialty or "",
        require_care_level=care_level if hard_filter_care_level else "",
        prefer_closer=prefer_closer,
    )
