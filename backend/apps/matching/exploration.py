"""Epsilon-greedy exploration slot for VEHMF top-K (Step 100).

Greedy ranking only ever exposes caregivers already near the top, which
starves new joiners and biases every model trained downstream. We reserve
one top-K slot (the last position) for a uniform draw from eligible
caregivers outside the greedy cut, with probability ``ε``.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import replace
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from .engine import RankedMatch


def exploration_epsilon() -> float:
    raw = getattr(settings, "MATCH_EXPLORATION_EPSILON", 0.0)
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return 0.0


def apply_exploration_slot(
    greedy: Sequence[RankedMatch],
    remainder: Sequence[RankedMatch],
    *,
    emergency: bool,
    epsilon: float | None = None,
    rng: random.Random | None = None,
) -> tuple[list[RankedMatch], bool]:
    """Replace the last greedy slot with one exploratory hit when ε fires.

    Returns ``(results, explored)``. Emergency runs and ``ε <= 0`` never explore.
    Requires at least one remainder candidate and a non-empty greedy list.
    """
    eps = exploration_epsilon() if epsilon is None else max(0.0, min(1.0, float(epsilon)))
    results = [replace(r, was_exploratory=False) for r in greedy]
    if emergency or eps <= 0 or not results or not remainder:
        return results, False

    rng = rng or random.Random()
    if rng.random() >= eps:
        return results, False

    pick = rng.choice(list(remainder))
    exploratory = replace(pick, was_exploratory=True)
    # Keep ranks 1..K-1 greedy; last slot is the exploration seat.
    out = results[:-1] + [exploratory]
    return out, True


def exposure_counts_from_rankings(runs: Sequence[Sequence[int]]) -> dict[int, int]:
    """Tally caregiver appearances across simulated top-K lists."""
    counts: dict[int, int] = {}
    for ranking in runs:
        for cid in ranking:
            counts[cid] = counts.get(cid, 0) + 1
    return counts
