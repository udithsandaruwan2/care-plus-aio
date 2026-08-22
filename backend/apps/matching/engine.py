"""VEHMF matching engine — CBF + CF + Geo + Trust fusion + XAI (Step 19).

Step 22 loads trained ALS CF when available; ``CF_ENABLED=false`` zeroes β and
redistributes AHP weight across CBF/geo/trust.

Step 100 reserves one top-K slot for epsilon-greedy exploration (off in emergencies).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace

import numpy as np
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point

from .ahp import get_ahp_weights, normalize_weights
from .caregiver_profile import listable_caregivers
from .cf_model import cf_model_info, get_cf_model, is_cf_active
from .embeddings import get_embedder, intent_to_text
from .exploration import apply_exploration_slot, exploration_epsilon
from .faiss_index import CaregiverIndex, load_index
from .i18n import format_match_explanation
from .models import CaregiverProfile, PatientProfile

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
    # Step 100 — True when this row filled the epsilon-greedy exploration slot.
    was_exploratory: bool = False


@dataclass(frozen=True)
class MatchOutput:
    results: list[RankedMatch]
    weights: tuple[float, float, float, float]
    query: str
    emergency: bool
    cf_enabled: bool = False
    cf_version: str | None = None
    embedding_backend: str = ""
    index_version: str = ""
    weights_source: str = "ahp"
    # Step 102 — A/B weight variant id (empty when experiment disabled).
    variant: str = ""
    filters: dict = field(default_factory=dict)


def match_run_provenance(out: MatchOutput) -> dict:
    """Fields persisted on ``MatchRun`` for replay (Step 79 / 102)."""
    return {
        "cf_version": out.cf_version or "",
        "embedding_backend": out.embedding_backend or "",
        "index_version": out.index_version or "",
        "weights_source": out.weights_source or "",
        "variant": out.variant or "",
        "filters": dict(out.filters or {}),
    }


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

    def _out(self, *, weights_source: str = "ahp", **kwargs) -> MatchOutput:
        return MatchOutput(
            embedding_backend=getattr(self.index, "backend", "") or "",
            index_version=getattr(self.index, "version", "") or "",
            weights_source=weights_source,
            **kwargs,
        )

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
            return self._out(
                results=[],
                weights=tuple(float(w) for w in self.W),
                query=query_text,
                emergency=emergency,
                cf_enabled=self._cf_info["enabled"],
                cf_version=self._cf_info["version"],
                weights_source="ahp_emergency" if emergency else "ahp",
            )

        weights_source = "ahp"
        variant = ""
        if weights is not None:
            weights_source = "explicit"
            W = np.asarray(normalize_weights(list(weights)), dtype=np.float32)
        elif prefer_closer and not emergency:
            W = np.asarray(normalize_weights([0.25, 0.05, 0.55, 0.15]), dtype=np.float32)
            weights_source = "prefer_closer"
        else:
            from .experiments import resolve_ab_weights

            city = ""
            if patient_id is not None:
                profile = PatientProfile.objects.filter(user_id=patient_id).only("city").first()
                if profile is not None:
                    city = profile.city or ""
            resolved = resolve_ab_weights(
                patient_id,
                emergency=emergency,
                city=city or None,
            )
            W = np.asarray(resolved.weights, dtype=np.float32)
            weights_source = resolved.weights_source
            variant = resolved.variant

        cf_active = is_cf_active(self.cf_model)
        W = _effective_weights(W, cf_active=cf_active)
        effective_weights = tuple(float(w) for w in W)

        # 1. CBF — FAISS inner product on L2-normalized vectors.
        qvec = get_embedder().embed([query_text])[0]
        pool = min(candidate_pool, self.index.size)
        cbf_hits = self.index.search(qvec, k=pool)
        if not cbf_hits:
            return self._out(
                results=[],
                weights=effective_weights,
                query=query_text,
                emergency=emergency,
                cf_enabled=cf_active,
                cf_version=self._cf_info["version"],
                weights_source=weights_source,
                variant=variant,
            )

        caregiver_ids = [cid for cid, _ in cbf_hits]

        # Soft presence (Step 20e): unavailable caregivers stay in the FAISS index
        # but are hidden from match top-N (browse can still show them via ?available=0).
        profiles = {
            p.id: p
            for p in listable_caregivers(
                CaregiverProfile.objects.filter(
                    id__in=caregiver_ids,
                    is_active=True,
                    is_available=True,
                    is_approved=True,
                )
            )
        }
        # Keep FAISS order but drop missing/inactive/unavailable/unapproved.
        ordered_ids = [cid for cid in caregiver_ids if cid in profiles]
        if not ordered_ids:
            return self._out(
                results=[],
                weights=effective_weights,
                query=query_text,
                emergency=emergency,
                cf_enabled=cf_active,
                cf_version=self._cf_info["version"],
                weights_source=weights_source,
                variant=variant,
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
            return self._out(
                results=[],
                weights=effective_weights,
                query=query_text,
                emergency=emergency,
                cf_enabled=cf_active,
                cf_version=self._cf_info["version"],
                weights_source=weights_source,
                variant=variant,
            )

        eligible_arr = np.asarray(eligible, dtype=np.int64)
        # Score-sorted full eligible list (before diversity / caps).
        order_all = np.argsort(-final[eligible_arr])

        def _row_match(i: int) -> RankedMatch:
            cid = ordered_ids[i]
            row = score_matrix[i]
            contributor = int(np.argmax(row * W))
            return RankedMatch(
                caregiver_id=cid,
                score=float(final[i]),
                cbf=float(row[0]),
                cf=float(row[1]),
                geo=float(row[2]),
                trust=float(row[3]),
                explanation=format_match_explanation(contributor, "en"),
                distance_m=distances.get(cid),
            )

        from .fairness import (
            exposure_cap,
            exposure_window_hours,
            filter_overexposed,
            mmr_lambda,
            mmr_rerank,
        )

        ranked_all = [_row_match(int(eligible_arr[int(loc)])) for loc in order_all]
        capped, dropped_ids = filter_overexposed(ranked_all, emergency=emergency)
        # Step 103 — MMR diversity (skipped in emergencies: keep pure relevance order).
        if emergency:
            greedy = capped[:top_k]
            mmr_applied = False
        else:
            greedy = mmr_rerank(capped, profiles, k=top_k)
            mmr_applied = True

        greedy_ids = {r.caregiver_id for r in greedy}
        remainder = [r for r in capped if r.caregiver_id not in greedy_ids]
        # Prefer lower-scored remainder first so exploration surfaces the long tail.
        remainder.sort(key=lambda r: r.score)

        eps = exploration_epsilon()
        results, explored = apply_exploration_slot(
            greedy,
            remainder,
            emergency=emergency,
            epsilon=eps,
        )

        return self._out(
            results=results,
            weights=effective_weights,
            query=query_text,
            emergency=emergency,
            cf_enabled=cf_active,
            cf_version=self._cf_info["version"],
            weights_source=weights_source,
            variant=variant,
            filters={
                "exploration_epsilon": eps,
                "explored": explored,
                "mmr_applied": mmr_applied,
                "mmr_lambda": mmr_lambda() if mmr_applied else None,
                "exposure_cap": exposure_cap(),
                "exposure_window_hours": exposure_window_hours(),
                "exposure_dropped": dropped_ids[:20],
            },
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
    out = eng.predict(
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
    filters = {
        "condition": condition or "",
        "language": language or "",
        "care_level": care_level or "",
        "query": query or "",
        "top_k": int(top_k),
        "max_distance_km": max_distance_km,
        "specialty": specialty or "",
        "prefer_closer": bool(prefer_closer),
        "hard_filter_language": bool(hard_filter_language),
        "hard_filter_care_level": bool(hard_filter_care_level),
        "longitude": longitude,
        "latitude": latitude,
        "patient_id": patient_id,
        **dict(out.filters or {}),
    }
    return replace(out, filters=filters)
