"""Online A/B assignment for VEHMF fusion weight variants (Step 102).

Deterministic user-level hashing assigns each patient to an active traffic
arm. Variant id is persisted on ``MatchRun.variant``. Arms are configured in
JSON (``WEIGHT_AB_CONFIG_PATH``) so a variant can be retired by setting
``active: false`` or ``traffic: 0`` without redeploying.

Stopping rule
-------------
Do **not** interpret the admin comparison view until every *active* arm has
at least ``min_runs_per_variant`` labelled MatchRuns **and** the experiment
window is at least ``min_days`` days old. Early peeks inflate false positives.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings

from apps.matching.ahp import normalize_weights
from apps.matching.weights_train import get_fusion_weights


def default_ab_config_path() -> Path:
    raw = getattr(settings, "WEIGHT_AB_CONFIG_PATH", "") or ""
    if raw:
        return Path(raw)
    return Path(settings.BASE_DIR).parent / "config" / "weight_ab.json"


def ab_enabled() -> bool:
    return bool(getattr(settings, "WEIGHT_AB_ENABLED", False))


def _default_config() -> dict[str, Any]:
    return {
        "experiment_id": "weight_ab_v1",
        "salt": getattr(settings, "WEIGHT_AB_SALT", "careplus-step102") or "careplus-step102",
        "min_runs_per_variant": 200,
        "min_days": 14,
        "variants": [
            {"id": "control", "traffic": 100, "active": True, "weights": None},
        ],
    }


def load_ab_config(*, force: bool = False) -> dict[str, Any]:
    path = default_ab_config_path()
    if not path.exists():
        return _default_config()
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_config()
    if not isinstance(doc, dict):
        return _default_config()
    # Fill defaults for missing keys.
    base = _default_config()
    base.update({k: v for k, v in doc.items() if v is not None})
    if not base.get("variants"):
        base["variants"] = _default_config()["variants"]
    if not base.get("salt"):
        base["salt"] = getattr(settings, "WEIGHT_AB_SALT", "careplus-step102")
    return base


def active_variants(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = config or load_ab_config()
    out = []
    for row in cfg.get("variants") or []:
        if not isinstance(row, dict):
            continue
        if not row.get("active", True):
            continue
        traffic = int(row.get("traffic") or 0)
        if traffic <= 0:
            continue
        vid = str(row.get("id") or "").strip()
        if not vid:
            continue
        out.append({**row, "id": vid, "traffic": traffic})
    return out


def assign_variant(user_id: int | None, *, config: dict[str, Any] | None = None) -> str:
    """Stable hash assignment across sessions for a given user id."""
    if user_id is None:
        return ""
    cfg = config or load_ab_config()
    arms = active_variants(cfg)
    if not arms:
        return ""
    total = sum(int(a["traffic"]) for a in arms)
    if total <= 0:
        return ""
    salt = str(cfg.get("salt") or "careplus-step102")
    digest = hashlib.sha256(f"{salt}:{int(user_id)}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % total
    cursor = 0
    for arm in arms:
        cursor += int(arm["traffic"])
        if bucket < cursor:
            return str(arm["id"])
    return str(arms[-1]["id"])


@dataclass(frozen=True)
class AbResolution:
    weights: tuple[float, float, float, float]
    weights_source: str
    variant: str


def resolve_ab_weights(
    user_id: int | None,
    *,
    emergency: bool = False,
    city: str | None = None,
) -> AbResolution:
    """Assign variant and return fusion weights (override or base)."""
    base, base_src = get_fusion_weights(emergency=emergency, city=city)
    if not ab_enabled() or user_id is None:
        return AbResolution(weights=base, weights_source=base_src, variant="")

    cfg = load_ab_config()
    variant = assign_variant(user_id, config=cfg)
    if not variant:
        return AbResolution(weights=base, weights_source=base_src, variant="")

    arm = next((a for a in (cfg.get("variants") or []) if str(a.get("id")) == variant), None)
    if not arm or not arm.get("active", True):
        # Retired mid-flight: still record historical assignment intent as empty override.
        return AbResolution(weights=base, weights_source=base_src, variant=variant)

    override = arm.get("weights")
    if override is None:
        return AbResolution(
            weights=base,
            weights_source=f"ab:{variant}",
            variant=variant,
        )
    try:
        vec = normalize_weights(override)
    except Exception:
        return AbResolution(weights=base, weights_source=base_src, variant=variant)
    return AbResolution(weights=vec, weights_source=f"ab:{variant}", variant=variant)


def stopping_rule_status(
    variant_stats: list[dict[str, Any]],
    *,
    window_days: int,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Whether it is safe to read A/B results (pre-specified mins)."""
    cfg = config or load_ab_config()
    min_runs = int(cfg.get("min_runs_per_variant") or 200)
    min_days = int(cfg.get("min_days") or 14)
    active_ids = {a["id"] for a in active_variants(cfg)}
    by_id = {str(r.get("variant")): r for r in variant_stats}

    reasons: list[str] = []
    if window_days < min_days:
        reasons.append(f"window_days={window_days} < min_days={min_days}")

    for vid in sorted(active_ids):
        n = int((by_id.get(vid) or {}).get("n_runs") or 0)
        if n < min_runs:
            reasons.append(f"{vid}: n_runs={n} < {min_runs}")

    ready = len(reasons) == 0 and bool(active_ids)
    return {
        "ready": ready,
        "min_runs_per_variant": min_runs,
        "min_days": min_days,
        "window_days": window_days,
        "reasons": reasons,
        "guidance": (
            "Results are ready for interpretation."
            if ready
            else "Do not interpret early — wait until every active arm meets sample and day minima."
        ),
    }
