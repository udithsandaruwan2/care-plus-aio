"""Analytic Hierarchy Process (AHP) weights for VEHMF fusion (Step 18).

Factors (order fixed for the engine)::

    [α, β, γ, δ] = [CBF, CF, Geo, Trust]

The principal eigenvector of a stakeholder pairwise matrix becomes the weight
vector. Consistency ratio (CR) must be < 0.1 for the survey to be accepted.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from django.conf import settings

FACTORS = ("cbf", "cf", "geo", "trust")
N = len(FACTORS)

# Saaty random-index table (n = matrix order).
_RI = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45}

# Default pairwise survey (research lean: clinical content > trust ≈ geo > CF).
# Rows/cols = CBF, CF, Geo, Trust. a_ij = how much more important i is than j.
DEFAULT_PAIRWISE = [
    [1, 5, 3, 2],  # CBF vs …
    [1 / 5, 1, 1 / 3, 1 / 4],  # CF vs …
    [1 / 3, 3, 1, 1],  # Geo vs …
    [1 / 2, 4, 1, 1],  # Trust vs …
]

# Emergency override used by dynamic re-weight (ARCHITECTURE Flow 2).
DEFAULT_EMERGENCY = [0.80, 0.05, 0.05, 0.10]


@dataclass(frozen=True)
class AhpResult:
    weights: tuple[float, float, float, float]
    lambda_max: float
    consistency_index: float
    consistency_ratio: float
    factors: tuple[str, ...] = FACTORS

    def as_dict(self) -> dict:
        d = asdict(self)
        d["weights"] = {
            name: round(w, 6) for name, w in zip(self.factors, self.weights, strict=True)
        }
        d["vector"] = [round(w, 6) for w in self.weights]
        return d

    @property
    def is_consistent(self) -> bool:
        return self.consistency_ratio < 0.1


class AhpError(ValueError):
    """Raised when the pairwise matrix is invalid or CR ≥ 0.1."""


def solve_ahp(pairwise: list[list[float]] | np.ndarray) -> AhpResult:
    """Return normalized principal-eigenvector weights + consistency stats."""
    a = np.asarray(pairwise, dtype=np.float64)
    if a.shape != (N, N):
        raise AhpError(f"pairwise matrix must be {N}×{N}, got {a.shape}")
    if np.any(a <= 0):
        raise AhpError("pairwise entries must be positive")

    # Reciprocal check (tolerance for float survey input).
    for i in range(N):
        for j in range(N):
            if abs(a[i, j] * a[j, i] - 1.0) > 1e-6:
                raise AhpError(f"matrix not reciprocal at ({i},{j})")

    eigenvalues, eigenvectors = np.linalg.eig(a)
    idx = int(np.argmax(eigenvalues.real))
    lambda_max = float(eigenvalues[idx].real)
    raw = np.abs(eigenvectors[:, idx].real)
    weights = raw / raw.sum()

    ci = (lambda_max - N) / (N - 1) if N > 1 else 0.0
    ri = _RI.get(N, 1.45)
    cr = float(ci / ri) if ri else 0.0

    result = AhpResult(
        weights=tuple(float(w) for w in weights),
        lambda_max=lambda_max,
        consistency_index=float(ci),
        consistency_ratio=cr,
    )
    if not result.is_consistent:
        raise AhpError(f"AHP consistency ratio too high: CR={cr:.4f} (need < 0.1)")
    return result


def normalize_weights(weights: list[float] | np.ndarray) -> tuple[float, float, float, float]:
    w = np.asarray(weights, dtype=np.float64).ravel()
    if w.shape != (N,):
        raise AhpError(f"weights must have length {N}, got {w.shape}")
    if np.any(w < 0):
        raise AhpError("weights must be non-negative")
    s = float(w.sum())
    if s <= 0:
        raise AhpError("weights must sum to a positive value")
    out = (w / s).astype(np.float64)
    return tuple(float(x) for x in out)


def default_config_path() -> Path:
    raw = getattr(settings, "AHP_WEIGHTS_PATH", "") or ""
    if raw:
        return Path(raw)
    # Prefer repo ``config/ahp_weights.json`` (mounted in Compose).
    return Path(settings.BASE_DIR).parent / "config" / "ahp_weights.json"


def build_config(
    pairwise: list[list[float]] | None = None,
    emergency: list[float] | None = None,
) -> dict:
    """Solve AHP and return a serializable config document."""
    matrix = pairwise if pairwise is not None else DEFAULT_PAIRWISE
    result = solve_ahp(matrix)
    emerg = normalize_weights(emergency if emergency is not None else DEFAULT_EMERGENCY)
    return {
        "factors": list(FACTORS),
        "pairwise": matrix,
        "weights": {name: round(w, 6) for name, w in zip(FACTORS, result.weights, strict=True)},
        "vector": [round(w, 6) for w in result.weights],
        "consistency_ratio": round(result.consistency_ratio, 6),
        "lambda_max": round(result.lambda_max, 6),
        "emergency_vector": [round(w, 6) for w in emerg],
        "emergency_weights": {name: round(w, 6) for name, w in zip(FACTORS, emerg, strict=True)},
    }


def write_config(path: Path | None = None, **kwargs) -> Path:
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = build_config(**kwargs)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path


def load_weights(*, emergency: bool = False) -> tuple[float, float, float, float]:
    """Load fusion weights from env override → JSON config → live AHP solve."""
    env_key = "AHP_EMERGENCY_WEIGHTS" if emergency else "AHP_WEIGHTS"
    override = getattr(settings, env_key, "") or ""
    if override:
        parts = [float(x.strip()) for x in override.split(",")]
        return normalize_weights(parts)

    path = default_config_path()
    if path.exists():
        doc = json.loads(path.read_text(encoding="utf-8"))
        key = "emergency_vector" if emergency else "vector"
        if key in doc:
            return normalize_weights(doc[key])
        # Older shape: named weights dict.
        named = doc.get("emergency_weights" if emergency else "weights")
        if named:
            return normalize_weights([named[f] for f in FACTORS])

    # No file yet — solve defaults in-process (and optionally persist).
    doc = build_config()
    return normalize_weights(doc["emergency_vector" if emergency else "vector"])


# Process-local cache so Step 19 can grab weights cheaply.
_CACHE: dict[str, tuple[float, float, float, float]] = {}


def get_ahp_weights(*, emergency: bool = False, refresh: bool = False) -> tuple[float, ...]:
    key = "emergency" if emergency else "normal"
    if refresh or key not in _CACHE:
        _CACHE[key] = load_weights(emergency=emergency)
    return _CACHE[key]


def reset_ahp_cache() -> None:
    _CACHE.clear()
