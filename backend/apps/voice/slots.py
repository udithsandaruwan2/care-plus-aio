"""Hashed n-gram multi-head slot classifier (Step 96).

Trains on ``VoiceIntent`` rows plus a seed corpus and vocab expansion; evaluates
on a hand-labelled si/ta/en holdout (honest eval — not Gemini labels). Artifacts
register as ``ModelKind.SLOT_CLASSIFIER`` with the same gated-promotion path as CF.

Lean CPU profile: character/word feature hashing + class-centroid / k-NN heads
(numpy only). Inference target < 50 ms per utterance.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from django.conf import settings

from apps.matching.models import ModelKind, ModelVersion
from apps.voice.models import CareLevel, Language, Urgency

logger = logging.getLogger(__name__)

SLOT_KEYS = ("condition", "language", "care_level", "urgency")
_TOKEN_RE = re.compile(r"[a-z0-9\u0d80-\u0dff\u0b80-\u0bff]+", re.I)
_DEFAULT_DIM = 2048
_CHAR_NS = (2, 3, 4)


def _ml_root() -> Path:
    """Locate ``ml/`` (Docker mounts repo ``ml`` at ``/ml``)."""
    for candidate in (
        Path("/ml"),
        Path(getattr(settings, "BASE_DIR", ".")).resolve().parent / "ml",
        Path(__file__).resolve().parents[3] / "ml",
    ):
        path = candidate.resolve()
        if (path / "data").is_dir():
            return path
    return Path(getattr(settings, "BASE_DIR", ".")).resolve().parent / "ml"


def artifact_root() -> Path:
    configured = (getattr(settings, "SLOT_ARTIFACT_DIR", "") or "").strip()
    if configured:
        return Path(configured)
    faiss = (getattr(settings, "FAISS_ARTIFACT_DIR", "") or "").strip()
    if faiss:
        return Path(faiss) / "slots"
    cf = (getattr(settings, "CF_ARTIFACT_DIR", "") or "").strip()
    if cf:
        return Path(cf).parent / "slots"
    return _ml_root() / "artifacts" / "slots"


def hand_holdout_path() -> Path:
    configured = (getattr(settings, "SLOT_HOLDOUT_PATH", "") or "").strip()
    if configured:
        return Path(configured)
    return _ml_root() / "data" / "slot_holdout_hand.json"


def train_seed_path() -> Path:
    configured = (getattr(settings, "SLOT_TRAIN_SEED_PATH", "") or "").strip()
    if configured:
        return Path(configured)
    return _ml_root() / "data" / "slot_train_seed.json"


def _blake_idx(token: str, dim: int) -> tuple[int, float]:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    idx = int.from_bytes(digest[:4], "little") % dim
    sign = 1.0 if digest[4] % 2 == 0 else -1.0
    return idx, sign


def featurize(texts: list[str], *, dim: int = _DEFAULT_DIM) -> np.ndarray:
    """Signed feature hashing over word tokens + character n-grams."""
    out = np.zeros((len(texts), dim), dtype=np.float32)
    for i, raw in enumerate(texts):
        text = (raw or "").strip().lower()
        if not text:
            continue
        for tok in _TOKEN_RE.findall(text):
            idx, sign = _blake_idx(f"w:{tok}", dim)
            out[i, idx] += sign
            for n in _CHAR_NS:
                if len(tok) < n:
                    continue
                for j in range(len(tok) - n + 1):
                    idx, sign = _blake_idx(f"c{n}:{tok[j : j + n]}", dim)
                    out[i, idx] += sign
        compact = re.sub(r"\s+", "", text)
        for n in _CHAR_NS:
            if len(compact) < n:
                continue
            for j in range(0, min(len(compact) - n + 1, 200), 1):
                idx, sign = _blake_idx(f"s{n}:{compact[j : j + n]}", dim)
                out[i, idx] += 0.5 * sign
        norm = float(np.linalg.norm(out[i]))
        if norm > 1e-8:
            out[i] /= norm
    return out


def _fit_centroids(X: np.ndarray, y: np.ndarray, n_classes: int) -> np.ndarray:
    """Class-mean prototypes in hashed feature space."""
    d = X.shape[1]
    centroids = np.zeros((n_classes, d), dtype=np.float32)
    for c in range(n_classes):
        mask = y == c
        if not np.any(mask):
            continue
        vec = X[mask].mean(axis=0)
        norm = float(np.linalg.norm(vec))
        if norm > 1e-8:
            vec = vec / norm
        centroids[c] = vec.astype(np.float32)
    return centroids


@dataclass
class SlotHead:
    labels: list[str]
    """Prototype matrix [C, D] and optional k-NN memory [N, D] + label indices."""
    centroids: np.ndarray
    prefer_nonempty: bool = False
    X_ref: np.ndarray | None = None
    y_ref: np.ndarray | None = None

    def predict_idx(self, X: np.ndarray) -> np.ndarray:
        if self.X_ref is not None and self.y_ref is not None and self.X_ref.size > 0:
            sims = X @ self.X_ref.T
            nn = np.argmax(sims, axis=1)
            return self.y_ref[nn].astype(np.int64)
        if not self.labels or self.centroids.size == 0:
            return np.zeros(X.shape[0], dtype=np.int64)
        sims = X @ self.centroids.T
        if not self.prefer_nonempty or "" not in self.labels:
            return np.argmax(sims, axis=1)
        empty_i = self.labels.index("")
        out = np.empty(X.shape[0], dtype=np.int64)
        for i in range(X.shape[0]):
            row = sims[i].copy()
            best = int(np.argmax(row))
            if best == empty_i:
                row[empty_i] = -1e9
                alt = int(np.argmax(row))
                if float(row[alt]) >= 0.02:
                    best = alt
            out[i] = best
        return out


@dataclass
class SlotClassifier:
    version: str
    dim: int
    heads: dict[str, SlotHead]
    metrics: dict[str, Any]

    def predict_one(self, text: str) -> dict[str, str]:
        X = featurize([text], dim=self.dim)
        out: dict[str, str] = {}
        for key in SLOT_KEYS:
            head = self.heads.get(key)
            if head is None or not head.labels:
                out[key] = ""
                continue
            idx = int(head.predict_idx(X)[0])
            out[key] = head.labels[idx]
        from apps.voice.extraction import detect_language, extract_stub

        stub = extract_stub(text)
        # Classifier owns condition; stub heuristics remain strong for level/urgency/language.
        out["language"] = detect_language(text) or stub.get("language") or out.get("language") or Language.ENGLISH
        out["care_level"] = stub.get("care_level") or out.get("care_level") or CareLevel.INTERMEDIATE
        out["urgency"] = stub.get("urgency") or out.get("urgency") or Urgency.ROUTINE
        return out

    def predict_many(self, texts: list[str]) -> list[dict[str, str]]:
        return [self.predict_one(t) for t in texts]


def _load_json_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "examples" in data:
        data = data["examples"]
    rows: list[dict[str, str]] = []
    for item in data or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("raw_text") or "").strip()
        if not text:
            continue
        rows.append(
            {
                "text": text,
                "condition": str(item.get("condition") or "").strip(),
                "language": str(item.get("language") or Language.ENGLISH).strip(),
                "care_level": str(item.get("care_level") or CareLevel.INTERMEDIATE).strip(),
                "urgency": str(item.get("urgency") or Urgency.ROUTINE).strip(),
            }
        )
    return rows


def _vocab_seed_rows() -> list[dict[str, str]]:
    """Expand SEED_CONDITIONS synonyms into labelled utterances."""
    rows: list[dict[str, str]] = []
    try:
        from apps.vocab.seed_data import SEED_CONDITIONS
    except Exception:  # noqa: BLE001
        return rows

    for slug, _canonical, synonyms, _notes in SEED_CONDITIONS:
        for lang_key, syns in (synonyms or {}).items():
            lang = {
                "en": Language.ENGLISH,
                "si": Language.SINHALA,
                "ta": Language.TAMIL,
            }.get(lang_key, Language.ENGLISH)
            for syn in syns or []:
                syn = (syn or "").strip()
                if not syn:
                    continue
                rows.append(
                    {
                        "text": syn,
                        "condition": slug,
                        "language": lang,
                        "care_level": CareLevel.INTERMEDIATE,
                        "urgency": Urgency.ROUTINE,
                    }
                )
                if lang == Language.ENGLISH:
                    rows.extend(
                        [
                            {
                                "text": f"I need care for {syn}",
                                "condition": slug,
                                "language": Language.ENGLISH,
                                "care_level": CareLevel.INTERMEDIATE,
                                "urgency": Urgency.ROUTINE,
                            },
                            {
                                "text": f"help with {syn} please",
                                "condition": slug,
                                "language": Language.ENGLISH,
                                "care_level": CareLevel.BASIC,
                                "urgency": Urgency.ROUTINE,
                            },
                            {
                                "text": f"urgent support for {syn}",
                                "condition": slug,
                                "language": Language.ENGLISH,
                                "care_level": CareLevel.ADVANCED,
                                "urgency": Urgency.URGENT,
                            },
                        ]
                    )
                elif lang == Language.SINHALA:
                    rows.append(
                        {
                            "text": f"{syn} තියෙනවා, උදව් ඕන",
                            "condition": slug,
                            "language": Language.SINHALA,
                            "care_level": CareLevel.INTERMEDIATE,
                            "urgency": Urgency.ROUTINE,
                        }
                    )
                elif lang == Language.TAMIL:
                    rows.append(
                        {
                            "text": f"{syn} உள்ளது உதவி வேண்டும்",
                            "condition": slug,
                            "language": Language.TAMIL,
                            "care_level": CareLevel.INTERMEDIATE,
                            "urgency": Urgency.ROUTINE,
                        }
                    )
    return rows


def load_training_rows(*, include_voice_intents: bool = True) -> list[dict[str, str]]:
    """Seed corpus + vocab expansion + optional VoiceIntent rows (Gemini-biased)."""
    rows = _load_json_rows(train_seed_path())
    rows.extend(_vocab_seed_rows())
    if include_voice_intents:
        try:
            from apps.voice.models import VoiceIntent

            for vi in VoiceIntent.objects.all().iterator(chunk_size=200):
                text = (vi.raw_text or "").strip()
                if not text:
                    continue
                rows.append(
                    {
                        "text": text,
                        "condition": (vi.condition or "").strip(),
                        "language": vi.language or Language.ENGLISH,
                        "care_level": vi.care_level or CareLevel.INTERMEDIATE,
                        "urgency": vi.urgency or Urgency.ROUTINE,
                    }
                )
        except Exception:  # noqa: BLE001
            logger.debug("slot_train.voice_intent_skip", exc_info=True)
    return rows


def load_hand_holdout() -> list[dict[str, str]]:
    """Hand-labelled si/ta/en set — honest evaluation (not Gemini-derived)."""
    return _load_json_rows(hand_holdout_path())


def evaluate_on_rows(
    classifier: SlotClassifier,
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    if not rows:
        return {
            "n": 0,
            "exact_match": 0.0,
            "per_slot": {k: 0.0 for k in SLOT_KEYS},
            "latency_ms_p50": 0.0,
            "latency_ms_p95": 0.0,
        }
    texts = [r["text"] for r in rows]
    t0 = time.perf_counter()
    preds = classifier.predict_many(texts)
    total_ms = (time.perf_counter() - t0) * 1000.0
    latencies: list[float] = []
    for text in texts[: min(32, len(texts))]:
        s = time.perf_counter()
        classifier.predict_one(text)
        latencies.append((time.perf_counter() - s) * 1000.0)

    correct = {k: 0 for k in SLOT_KEYS}
    exact = 0
    for gold, pred in zip(rows, preds, strict=True):
        slot_ok = True
        for k in SLOT_KEYS:
            if gold.get(k, "") == pred.get(k, ""):
                correct[k] += 1
            else:
                slot_ok = False
        if slot_ok:
            exact += 1
    n = len(rows)
    latencies_sorted = sorted(latencies) if latencies else [total_ms / max(n, 1)]
    p50 = latencies_sorted[len(latencies_sorted) // 2]
    p95 = latencies_sorted[min(len(latencies_sorted) - 1, int(0.95 * len(latencies_sorted)))]
    return {
        "n": n,
        "exact_match": exact / n,
        "per_slot": {k: correct[k] / n for k in SLOT_KEYS},
        "latency_ms_p50": float(p50),
        "latency_ms_p95": float(p95),
        "latency_ms_batch_mean": float(total_ms / n),
    }


def evaluate_stub_on_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    from apps.voice.extraction import extract_stub

    if not rows:
        return {"n": 0, "exact_match": 0.0, "per_slot": {k: 0.0 for k in SLOT_KEYS}}
    correct = {k: 0 for k in SLOT_KEYS}
    exact = 0
    for gold in rows:
        pred = extract_stub(gold["text"])
        slot_ok = True
        for k in SLOT_KEYS:
            if gold.get(k, "") == str(pred.get(k) or ""):
                correct[k] += 1
            else:
                slot_ok = False
        if slot_ok:
            exact += 1
    n = len(rows)
    return {
        "n": n,
        "exact_match": exact / n,
        "per_slot": {k: correct[k] / n for k in SLOT_KEYS},
    }


def _fit_classifier(rows: list[dict[str, str]], *, dim: int = _DEFAULT_DIM) -> SlotClassifier:
    texts = [r["text"] for r in rows]
    X = featurize(texts, dim=dim)
    heads: dict[str, SlotHead] = {}
    for key in SLOT_KEYS:
        labels = sorted({(r.get(key) or "") for r in rows})
        if not labels:
            heads[key] = SlotHead(labels=[], centroids=np.zeros((0, dim), dtype=np.float32))
            continue
        label_to_i = {lab: i for i, lab in enumerate(labels)}
        y = np.array([label_to_i[r.get(key) or ""] for r in rows], dtype=np.int64)
        # Condition uses k-NN memory (paraphrases); other slots keep compact centroids.
        if key == "condition":
            heads[key] = SlotHead(
                labels=labels,
                centroids=_fit_centroids(X, y, len(labels)),
                prefer_nonempty=True,
                X_ref=X.astype(np.float32),
                y_ref=y.astype(np.int64),
            )
        else:
            heads[key] = SlotHead(
                labels=labels,
                centroids=_fit_centroids(X, y, len(labels)),
                prefer_nonempty=False,
            )
    return SlotClassifier(version="unversioned", dim=dim, heads=heads, metrics={})


def _write_artifact(classifier: SlotClassifier, version: str, metrics: dict) -> Path:
    root = artifact_root()
    version_dir = root / f"v{version}"
    version_dir.mkdir(parents=True, exist_ok=True)
    heads_payload: dict[str, Any] = {}
    for key, head in classifier.heads.items():
        entry: dict[str, Any] = {
            "labels": head.labels,
            "centroids": head.centroids.tolist(),
        }
        if head.X_ref is not None and head.y_ref is not None:
            knn_path = version_dir / f"{key}_knn.npz"
            np.savez_compressed(knn_path, X=head.X_ref, y=head.y_ref)
            entry["knn_file"] = knn_path.name
        heads_payload[key] = entry
    payload = {
        "version": version,
        "dim": classifier.dim,
        "heads": heads_payload,
        "metrics": metrics,
        "trained_at": datetime.now(UTC).isoformat(),
    }
    (version_dir / "model.json").write_text(json.dumps(payload), encoding="utf-8")
    meta = {
        "version": version,
        "kind": ModelKind.SLOT_CLASSIFIER,
        "metrics": metrics,
        "rows_trained_on": int(metrics.get("rows_trained_on") or 0),
    }
    (version_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return version_dir


def load_slot_classifier_from_dir(version_dir: Path) -> SlotClassifier | None:
    path = version_dir / "model.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    heads: dict[str, SlotHead] = {}
    for key, raw in (payload.get("heads") or {}).items():
        cents = raw.get("centroids")
        if cents is None and "W" in raw:
            cents = raw.get("W")
        x_ref = y_ref = None
        knn_name = raw.get("knn_file")
        if knn_name:
            knn_path = version_dir / str(knn_name)
            if knn_path.is_file():
                packed = np.load(knn_path)
                x_ref = packed["X"].astype(np.float32)
                y_ref = packed["y"].astype(np.int64)
        elif raw.get("X_ref") is not None:
            x_ref = np.asarray(raw["X_ref"], dtype=np.float32)
            y_ref = np.asarray(raw.get("y_ref") or [], dtype=np.int64)
        heads[key] = SlotHead(
            labels=list(raw.get("labels") or []),
            centroids=np.asarray(cents or [], dtype=np.float32),
            prefer_nonempty=(key == "condition"),
            X_ref=x_ref,
            y_ref=y_ref,
        )
    return SlotClassifier(
        version=str(payload.get("version") or version_dir.name.lstrip("v")),
        dim=int(payload.get("dim") or _DEFAULT_DIM),
        heads=heads,
        metrics=dict(payload.get("metrics") or {}),
    )


_ACTIVE: SlotClassifier | None = None


def load_slot_classifier(*, force: bool = False) -> SlotClassifier | None:
    global _ACTIVE
    if _ACTIVE is not None and not force:
        return _ACTIVE
    root = artifact_root()
    current = root / "current.json"
    version = ""
    if current.is_file():
        try:
            version = str(json.loads(current.read_text(encoding="utf-8")).get("version") or "")
        except json.JSONDecodeError:
            version = ""
    if not version:
        row = ModelVersion.objects.filter(kind=ModelKind.SLOT_CLASSIFIER, is_active=True).first()
        if row:
            version = row.version
    if not version:
        _ACTIVE = None
        return None
    clf = load_slot_classifier_from_dir(root / f"v{version}")
    _ACTIVE = clf
    return clf


def extract_with_classifier(
    text: str,
    hint_language: str | None = None,
    *,
    classifier: SlotClassifier | None = None,
) -> dict | None:
    """Return intent dict if an active classifier is available, else None."""
    clf = classifier if classifier is not None else load_slot_classifier()
    if clf is None:
        return None
    slots = clf.predict_one(text)
    language = slots.get("language") or Language.ENGLISH
    if hint_language in Language.values and not slots.get("language"):
        language = hint_language
    from apps.voice.extraction import detect_languages

    detected = detect_languages(text)
    if language not in detected:
        detected = [language, *[lng for lng in detected if lng != language]]
    return {
        "condition": slots.get("condition") or "",
        "language": language,
        "languages": detected,
        "care_level": slots.get("care_level") or CareLevel.INTERMEDIATE,
        "urgency": slots.get("urgency") or Urgency.ROUTINE,
        "raw_text": text,
        "source": "slot_classifier",
        "model_version": clf.version,
    }


def promote_slot_version(version: str, *, force: bool = False, reason: str = "manual") -> dict:
    ver = version.strip().lstrip("v")
    root = artifact_root()
    version_dir = root / f"v{ver}"
    if not version_dir.is_dir():
        raise ValueError(f"Slot classifier artifact missing: {version_dir}")

    if not force and getattr(settings, "SLOT_GATED_PROMOTION", True):
        return decide_and_maybe_promote_slots(version=ver, version_dir=version_dir, force=False)

    clf = load_slot_classifier_from_dir(version_dir)
    if clf is None:
        raise ValueError(f"Invalid slot classifier artifact under {version_dir}")

    from apps.matching.model_registry import register_model_version

    meta_path = version_dir / "meta.json"
    metrics: dict = {}
    rows = 0
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        metrics = dict(meta.get("metrics") or {})
        rows = int(meta.get("rows_trained_on") or metrics.get("rows_trained_on") or 0)

    register_model_version(
        kind=ModelKind.SLOT_CLASSIFIER,
        version=ver,
        rows_trained_on=rows,
        metrics={**metrics, "promote_reason": reason},
        artifact_path=str(version_dir),
        activate=True,
    )
    (root / "current.json").write_text(
        json.dumps({"version": ver, "reason": reason}, indent=2),
        encoding="utf-8",
    )
    global _ACTIVE
    _ACTIVE = clf
    _ACTIVE.version = ver
    return {
        "promoted": True,
        "reason": reason,
        "candidate_version": ver,
    }


def decide_and_maybe_promote_slots(
    *,
    version: str,
    version_dir: Path,
    force: bool = False,
) -> dict[str, Any]:
    gated = getattr(settings, "SLOT_GATED_PROMOTION", True)
    margin = float(getattr(settings, "SLOT_PROMOTE_MARGIN", 0.02))
    metric = str(getattr(settings, "SLOT_PROMOTE_METRIC", "exact_match"))

    candidate = load_slot_classifier_from_dir(version_dir)
    if candidate is None:
        raise ValueError(f"Candidate slot artifact missing under {version_dir}")

    holdout = load_hand_holdout()
    cand_report = evaluate_on_rows(candidate, holdout)

    def _score(report: dict) -> float:
        if metric == "exact_match":
            return float(report.get("exact_match") or 0.0)
        per = report.get("per_slot") or {}
        if metric in per:
            return float(per[metric])
        if metric == "macro_slot":
            vals = [float(per.get(k) or 0.0) for k in SLOT_KEYS]
            return sum(vals) / max(len(vals), 1)
        return float(report.get("exact_match") or 0.0)

    cand_score = _score(cand_report)
    stub_report = evaluate_stub_on_rows(holdout)
    stub_score = _score(stub_report)

    incumbent = load_slot_classifier(force=True)
    incumbent_version = incumbent.version if incumbent else None

    if incumbent is None:
        # Cold start still requires beating the rule stub (Step 96 acceptance).
        if cand_score >= stub_score + margin or force or not gated:
            promote_slot_version(version, force=True, reason="cold_start")
            return {
                "promoted": True,
                "reason": "cold_start",
                "incumbent_version": None,
                "candidate_version": version,
                "candidate_score": cand_score,
                "stub_score": stub_score,
                "metric": metric,
                "margin": margin,
                "candidate_metrics": cand_report,
                "stub_metrics": stub_report,
            }
        return {
            "promoted": False,
            "reason": "below_stub",
            "incumbent_version": None,
            "candidate_version": version,
            "candidate_score": cand_score,
            "stub_score": stub_score,
            "metric": metric,
            "margin": margin,
            "candidate_metrics": cand_report,
            "stub_metrics": stub_report,
        }

    if force or not gated:
        reason = "force" if force else "gated_disabled"
        promote_slot_version(version, force=True, reason=reason)
        return {
            "promoted": True,
            "reason": reason,
            "incumbent_version": incumbent_version,
            "candidate_version": version,
            "candidate_score": cand_score,
            "stub_score": stub_score,
            "metric": metric,
            "margin": margin,
            "candidate_metrics": cand_report,
            "stub_metrics": stub_report,
        }

    inc_report = evaluate_on_rows(incumbent, holdout)
    inc_score = _score(inc_report)
    beats_stub = cand_score >= stub_score + margin
    beats_inc = cand_score >= inc_score + margin

    if beats_inc and beats_stub:
        promote_slot_version(version, force=True, reason="holdout_win")
        return {
            "promoted": True,
            "reason": "holdout_win",
            "incumbent_version": incumbent_version,
            "candidate_version": version,
            "candidate_score": cand_score,
            "incumbent_score": inc_score,
            "stub_score": stub_score,
            "metric": metric,
            "margin": margin,
            "candidate_metrics": cand_report,
            "incumbent_metrics": inc_report,
            "stub_metrics": stub_report,
        }

    reason = "below_margin" if not beats_inc else "below_stub"
    logger.info(
        "slot_promote.rejected",
        extra={
            "reason": reason,
            "candidate_version": version,
            "incumbent_version": incumbent_version,
            "candidate_score": cand_score,
            "incumbent_score": inc_score,
            "stub_score": stub_score,
        },
    )
    return {
        "promoted": False,
        "reason": reason,
        "incumbent_version": incumbent_version,
        "candidate_version": version,
        "candidate_score": cand_score,
        "incumbent_score": inc_score,
        "stub_score": stub_score,
        "metric": metric,
        "margin": margin,
        "candidate_metrics": cand_report,
        "incumbent_metrics": inc_report,
        "stub_metrics": stub_report,
    }


def train_slot_classifier(
    *,
    force: bool = False,
    include_voice_intents: bool = True,
    dim: int = _DEFAULT_DIM,
) -> dict[str, Any]:
    """Train, write artifact, evaluate hand holdout, gated-promote."""
    rows = load_training_rows(include_voice_intents=include_voice_intents)
    if len(rows) < 8:
        raise ValueError(
            f"Need at least 8 training rows (seed + VoiceIntent); got {len(rows)}. "
            f"Expected seed at {train_seed_path()}"
        )

    version = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    classifier = _fit_classifier(rows, dim=dim)
    classifier.version = version

    holdout = load_hand_holdout()
    holdout_report = evaluate_on_rows(classifier, holdout)
    stub_report = evaluate_stub_on_rows(holdout)
    metrics = {
        "rows_trained_on": len(rows),
        "holdout": holdout_report,
        "stub_holdout": stub_report,
        "exact_match": holdout_report.get("exact_match", 0.0),
        "beats_stub": float(holdout_report.get("exact_match") or 0)
        > float(stub_report.get("exact_match") or 0),
    }
    version_dir = _write_artifact(classifier, version, metrics)

    from apps.matching.model_registry import register_model_version

    register_model_version(
        kind=ModelKind.SLOT_CLASSIFIER,
        version=version,
        rows_trained_on=len(rows),
        metrics=metrics,
        artifact_path=str(version_dir),
        activate=False,
    )

    decision = decide_and_maybe_promote_slots(
        version=version,
        version_dir=version_dir,
        force=force,
    )
    return {
        "version": version,
        "rows_trained_on": len(rows),
        "artifact_dir": str(version_dir),
        "metrics": metrics,
        "promotion": decision,
    }
