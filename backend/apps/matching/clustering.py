"""Caregiver / intent embedding clusters for CF cold-start (Step 99).

Caregivers absent from trained ALS item factors currently score CF 0.0.
We cluster CBF embeddings, average the CF vectors of trained members per
cluster, and seed missing caregivers with that cluster mean until they
accumulate real interactions.

Intent embeddings are clustered to surface demand groupings that can feed
back into the condition vocabulary as inactive draft terms.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
from django.conf import settings
from scipy.cluster.vq import kmeans2

from apps.matching.cf_model import AlsCFModel, cf_artifact_dir
from apps.matching.embeddings import get_embedder, intent_to_text, profile_to_text
from apps.matching.models import EMBEDDING_DIM, CaregiverProfile, MatchRun
from apps.vocab.models import ConditionTerm
from apps.vocab.resolver import active_slugs, clear_resolver_cache, resolve_condition

ClusterKind = Literal["caregiver", "intent"]


def cluster_artifact_dir() -> Path:
    raw = getattr(settings, "CLUSTER_ARTIFACT_DIR", "") or ""
    if raw:
        path = Path(raw)
    else:
        path = cf_artifact_dir() / "clusters"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _default_k(n: int, configured: int | None) -> int:
    if configured is not None and configured > 0:
        return max(1, min(configured, n))
    # Heuristic: ~sqrt(n), capped
    return max(1, min(int(round(n**0.5)), 12, n))


def _l2_rows(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (mat / norms).astype(np.float32)


@dataclass
class ClusterAssignment:
    kind: ClusterKind
    n_clusters: int
    labels: dict[int, int]  # entity_id → cluster_id
    centroids: np.ndarray  # (K, dim)
    member_ids: dict[int, list[int]] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "n_clusters": self.n_clusters,
            "labels": {str(k): int(v) for k, v in self.labels.items()},
            "centroids": self.centroids.astype(np.float32).tolist(),
            "member_ids": {str(k): [int(x) for x in v] for k, v in self.member_ids.items()},
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> ClusterAssignment:
        labels = {int(k): int(v) for k, v in (doc.get("labels") or {}).items()}
        member_ids = {
            int(k): [int(x) for x in v] for k, v in (doc.get("member_ids") or {}).items()
        }
        centroids = np.asarray(doc.get("centroids") or [], dtype=np.float32)
        return cls(
            kind=doc["kind"],
            n_clusters=int(doc["n_clusters"]),
            labels=labels,
            centroids=centroids,
            member_ids=member_ids,
            meta=dict(doc.get("meta") or {}),
        )


def persist_clusters(assignment: ClusterAssignment, *, path: Path | None = None) -> Path:
    out = path or (cluster_artifact_dir() / f"{assignment.kind}_clusters.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(assignment.to_dict(), indent=2), encoding="utf-8")
    return out


def load_clusters(kind: ClusterKind, *, path: Path | None = None) -> ClusterAssignment | None:
    target = path or (cluster_artifact_dir() / f"{kind}_clusters.json")
    if not target.exists():
        return None
    return ClusterAssignment.from_dict(json.loads(target.read_text(encoding="utf-8")))


def _run_kmeans(vectors: np.ndarray, k: int, *, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Return (centroids (K,d), labels (N,))."""
    n = vectors.shape[0]
    k = max(1, min(k, n))
    if k == 1:
        centroid = vectors.mean(axis=0, keepdims=True).astype(np.float32)
        return centroid, np.zeros(n, dtype=np.int32)
    # Hash embeddings are sparse; skip whiten (many zero-std columns) and
    # cluster in the original L2-normalized space.
    data = vectors.astype(np.float64)
    _centroids, labels = kmeans2(data, k, minit="++", seed=seed, missing="warn")
    centroids = np.zeros((k, vectors.shape[1]), dtype=np.float32)
    for c in range(k):
        mask = labels == c
        if not np.any(mask):
            centroids[c] = vectors.mean(axis=0)
        else:
            centroids[c] = vectors[mask].mean(axis=0)
    return _l2_rows(centroids), labels.astype(np.int32)


def assign_to_nearest(vector: np.ndarray, centroids: np.ndarray) -> int:
    if centroids.size == 0:
        return 0
    v = np.asarray(vector, dtype=np.float32).reshape(-1)
    sims = centroids @ v
    return int(np.argmax(sims))


def cluster_caregiver_embeddings(
    *,
    k: int | None = None,
    random_state: int = 42,
) -> ClusterAssignment:
    """Cluster active caregivers that already have stored CBF embeddings."""
    configured = k if k is not None else getattr(settings, "CLUSTER_CAREGIVER_K", 0) or None
    rows: list[tuple[int, np.ndarray, CaregiverProfile]] = []
    for cg in CaregiverProfile.objects.filter(is_active=True).iterator():
        emb = list(cg.embedding or [])
        if len(emb) != EMBEDDING_DIM:
            # Build on the fly from profile text when FAISS has not run yet.
            text = profile_to_text(cg)
            if not text.strip():
                continue
            vec = get_embedder().embed([text])[0]
        else:
            vec = np.asarray(emb, dtype=np.float32)
        rows.append((cg.id, vec, cg))

    if not rows:
        empty = ClusterAssignment(
            kind="caregiver",
            n_clusters=0,
            labels={},
            centroids=np.zeros((0, EMBEDDING_DIM), dtype=np.float32),
            meta={"note": "no caregivers with embeddings"},
        )
        return empty

    ids = [r[0] for r in rows]
    mat = _l2_rows(np.stack([r[1] for r in rows], axis=0))
    k_eff = _default_k(len(rows), configured)
    centroids, labels = _run_kmeans(mat, k_eff, seed=random_state)

    label_map = {cid: int(lab) for cid, lab in zip(ids, labels)}
    members: dict[int, list[int]] = defaultdict(list)
    for cid, lab in label_map.items():
        members[lab].append(cid)

    # Per-cluster specialty / language summaries for admin.
    cluster_meta: dict[str, Any] = {"clusters": {}}
    by_id = {r[0]: r[2] for r in rows}
    for lab, member_list in members.items():
        specs: Counter[str] = Counter()
        langs: Counter[str] = Counter()
        for mid in member_list:
            cg = by_id[mid]
            for s in cg.specialties or []:
                specs[str(s).lower()] += 1
            for lang in cg.languages or []:
                langs[str(lang)] += 1
        cluster_meta["clusters"][str(lab)] = {
            "size": len(member_list),
            "top_specialties": [s for s, _ in specs.most_common(5)],
            "top_languages": [s for s, _ in langs.most_common(3)],
            "sample_ids": member_list[:8],
        }

    return ClusterAssignment(
        kind="caregiver",
        n_clusters=int(centroids.shape[0]),
        labels=label_map,
        centroids=centroids,
        member_ids={int(k): v for k, v in members.items()},
        meta=cluster_meta,
    )


def _intent_rows(*, limit: int = 500) -> list[tuple[int, str, str]]:
    """Collect (entity_id, text, condition_label) from MatchRun + VoiceIntent."""
    rows: list[tuple[int, str, str]] = []
    # MatchRun ids are positive; VoiceIntent use negative ids to avoid collision.
    for run in MatchRun.objects.order_by("-created_at")[:limit]:
        text = intent_to_text(
            condition=run.condition or "",
            language=run.language or "",
            care_level=run.care_level or "",
            extra=run.query or "",
        )
        if text.strip():
            rows.append((int(run.id), text, (run.condition or "").strip()))

    try:
        from apps.voice.models import VoiceIntent

        for intent in VoiceIntent.objects.order_by("-ts")[:limit]:
            cond = intent.condition or ""
            text = intent_to_text(
                condition=cond,
                language=intent.language or "",
                care_level=intent.care_level or "",
                extra=intent.raw_text or "",
            )
            if text.strip():
                rows.append((-int(intent.id), text, cond.strip()))
    except Exception:
        pass
    return rows


def cluster_intent_embeddings(
    *,
    k: int | None = None,
    random_state: int = 42,
    limit: int = 500,
) -> ClusterAssignment:
    configured = k if k is not None else getattr(settings, "CLUSTER_INTENT_K", 0) or None
    rows = _intent_rows(limit=limit)
    if len(rows) < 2:
        return ClusterAssignment(
            kind="intent",
            n_clusters=0,
            labels={},
            centroids=np.zeros((0, EMBEDDING_DIM), dtype=np.float32),
            meta={"note": "insufficient intent rows", "n_rows": len(rows)},
        )

    texts = [r[1] for r in rows]
    mat = _l2_rows(np.asarray(get_embedder().embed(texts), dtype=np.float32))
    k_eff = _default_k(len(rows), configured)
    centroids, labels = _run_kmeans(mat, k_eff, seed=random_state)

    label_map = {eid: int(lab) for (eid, _, _), lab in zip(rows, labels)}
    members: dict[int, list[int]] = defaultdict(list)
    for eid, lab in label_map.items():
        members[lab].append(eid)

    cluster_meta: dict[str, Any] = {"clusters": {}}
    cond_by_id = {r[0]: r[2] for r in rows}
    text_by_id = {r[0]: r[1] for r in rows}
    for lab, member_list in members.items():
        phrases: Counter[str] = Counter()
        for mid in member_list:
            phrase = (cond_by_id.get(mid) or "").strip().lower()
            if phrase:
                phrases[phrase] += 1
        samples = [text_by_id[m] for m in member_list[:5] if m in text_by_id]
        cluster_meta["clusters"][str(lab)] = {
            "size": len(member_list),
            "top_conditions": [p for p, _ in phrases.most_common(5)],
            "sample_texts": samples,
            "sample_ids": member_list[:8],
        }

    return ClusterAssignment(
        kind="intent",
        n_clusters=int(centroids.shape[0]),
        labels=label_map,
        centroids=centroids,
        member_ids={int(k): v for k, v in members.items()},
        meta=cluster_meta,
    )


def build_cf_cold_start_vectors(
    model: AlsCFModel,
    caregiver_clusters: ClusterAssignment,
) -> dict[int, np.ndarray]:
    """Map caregivers missing from ALS to their cluster's mean item factor."""
    if caregiver_clusters.n_clusters <= 0 or model.item_factors.size == 0:
        return {}

    trained_idx = {cid: i for i, cid in enumerate(model.caregiver_ids)}
    trained = set(trained_idx)
    # Cluster → mean factor over trained members.
    cluster_avg: dict[int, np.ndarray] = {}
    global_mean = model.item_factors.mean(axis=0).astype(np.float32)
    for lab, members in caregiver_clusters.member_ids.items():
        vecs = [model.item_factors[trained_idx[cid]] for cid in members if cid in trained]
        if vecs:
            cluster_avg[int(lab)] = np.mean(np.stack(vecs, axis=0), axis=0).astype(np.float32)
        else:
            cluster_avg[int(lab)] = global_mean.copy()

    cold: dict[int, np.ndarray] = {}
    for cid, lab in caregiver_clusters.labels.items():
        if cid in trained:
            continue
        cold[int(cid)] = cluster_avg.get(int(lab), global_mean).copy()

    # Also seed any active caregiver with an embedding but not yet labeled
    # (joined after last cluster build) via nearest centroid.
    if caregiver_clusters.centroids.size:
        for cg in CaregiverProfile.objects.filter(is_active=True).iterator():
            if cg.id in trained or cg.id in cold:
                continue
            emb = list(cg.embedding or [])
            if len(emb) != EMBEDDING_DIM:
                text = profile_to_text(cg)
                if not text.strip():
                    continue
                vec = get_embedder().embed([text])[0]
            else:
                vec = np.asarray(emb, dtype=np.float32)
            lab = assign_to_nearest(vec, caregiver_clusters.centroids)
            cold[int(cg.id)] = cluster_avg.get(lab, global_mean).copy()

    return cold


def persist_cold_start_vectors(
    factors: dict[int, np.ndarray],
    *,
    path: Path | None = None,
) -> Path:
    out = path or (cluster_artifact_dir() / "cf_cold_start.npz")
    out.parent.mkdir(parents=True, exist_ok=True)
    if not factors:
        # Empty placeholder so loaders stay simple.
        np.savez_compressed(out, ids=np.array([], dtype=np.int64), factors=np.zeros((0, 1), dtype=np.float32))
        return out
    ids = np.array(sorted(factors.keys()), dtype=np.int64)
    mat = np.stack([factors[int(i)] for i in ids], axis=0).astype(np.float32)
    np.savez_compressed(out, ids=ids, factors=mat)
    return out


def load_cold_start_vectors(*, path: Path | None = None) -> dict[int, np.ndarray]:
    target = path or (cluster_artifact_dir() / "cf_cold_start.npz")
    if not target.exists():
        return {}
    data = np.load(target)
    ids = data["ids"]
    factors = data["factors"]
    if ids.size == 0:
        return {}
    return {int(i): factors[j].astype(np.float32) for j, i in enumerate(ids)}


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    s = _SLUG_RE.sub("-", (text or "").strip().lower()).strip("-")
    return (s or "cluster-condition")[:64]


def suggest_vocab_from_intent_clusters(
    assignment: ClusterAssignment,
) -> list[dict[str, Any]]:
    """Propose condition terms from intent cluster labels; flag unknowns."""
    known = set(active_slugs())
    suggestions: list[dict[str, Any]] = []
    clusters = (assignment.meta or {}).get("clusters") or {}
    for lab_str, info in clusters.items():
        tops = list(info.get("top_conditions") or [])
        samples = list(info.get("sample_texts") or [])
        # Prefer the most common free-text condition; fall back to first sample token.
        label = tops[0] if tops else (samples[0].split()[0] if samples else "")
        if not label:
            continue
        slug, canonical = resolve_condition(label)
        already = bool(slug) and slug in known
        proposed_slug = slug or _slugify(label)
        proposed_canonical = canonical or label.title()
        suggestions.append(
            {
                "cluster_id": int(lab_str),
                "proposed_slug": proposed_slug,
                "canonical_en": proposed_canonical,
                "synonyms": {"en": sorted({label, *(tops[:4])})},
                "sample_phrases": samples[:5],
                "already_in_vocab": already,
                "size": int(info.get("size") or 0),
            }
        )
    return suggestions


def apply_vocab_suggestions(
    suggestions: list[dict[str, Any]],
    *,
    create_drafts: bool = True,
) -> list[ConditionTerm]:
    """Create inactive ConditionTerm drafts for novel intent clusters."""
    created: list[ConditionTerm] = []
    if not create_drafts:
        return created
    for sug in suggestions:
        if sug.get("already_in_vocab"):
            continue
        slug = sug["proposed_slug"]
        if ConditionTerm.objects.filter(slug=slug).exists():
            continue
        term = ConditionTerm.objects.create(
            slug=slug,
            canonical_en=sug["canonical_en"],
            synonyms=sug.get("synonyms") or {},
            active=False,
            notes="step99-intent-cluster",
        )
        created.append(term)
    if created:
        clear_resolver_cache()
    return created


def build_and_persist_all(
    *,
    caregiver_k: int | None = None,
    intent_k: int | None = None,
    create_vocab_drafts: bool = True,
    cf_model: AlsCFModel | None = None,
) -> dict[str, Any]:
    """Build caregiver + intent clusters, cold-start vectors, and vocab drafts."""
    from apps.matching.cf_model import load_cf_model, reset_cf_cache

    cg = cluster_caregiver_embeddings(k=caregiver_k)
    persist_clusters(cg)
    intent = cluster_intent_embeddings(k=intent_k)
    persist_clusters(intent)

    model = cf_model or load_cf_model(force=True)
    cold: dict[int, np.ndarray] = {}
    if model is not None:
        cold = build_cf_cold_start_vectors(model, cg)
        persist_cold_start_vectors(cold)
        reset_cf_cache()

    suggestions = suggest_vocab_from_intent_clusters(intent)
    drafts = apply_vocab_suggestions(suggestions, create_drafts=create_vocab_drafts)
    novel = [s for s in suggestions if not s.get("already_in_vocab")]

    return {
        "caregiver_clusters": cg.n_clusters,
        "caregiver_members": len(cg.labels),
        "intent_clusters": intent.n_clusters,
        "intent_members": len(intent.labels),
        "cold_start_seeded": len(cold),
        "vocab_suggestions": len(suggestions),
        "vocab_novel": len(novel),
        "vocab_drafts_created": len(drafts),
        "novel_slugs": [s["proposed_slug"] for s in novel[:10]],
    }


def clusters_admin_payload() -> dict[str, Any]:
    """JSON payload for GET /api/v1/admin/clusters/."""
    cg = load_clusters("caregiver")
    intent = load_clusters("intent")
    cold = load_cold_start_vectors()
    suggestions = suggest_vocab_from_intent_clusters(intent) if intent else []
    return {
        "caregiver": None
        if cg is None
        else {
            "n_clusters": cg.n_clusters,
            "n_members": len(cg.labels),
            "clusters": (cg.meta or {}).get("clusters") or {},
        },
        "intent": None
        if intent is None
        else {
            "n_clusters": intent.n_clusters,
            "n_members": len(intent.labels),
            "clusters": (intent.meta or {}).get("clusters") or {},
            "vocab_suggestions": suggestions,
        },
        "cold_start_seeded": len(cold),
    }
