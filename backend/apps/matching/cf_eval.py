"""Offline ranking metrics for CF blend evaluation (Step 22)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def dcg_at_k(relevances: Sequence[float], k: int) -> float:
    k = min(k, len(relevances))
    if k <= 0:
        return 0.0
    total = 0.0
    for i in range(k):
        rel = relevances[i]
        if rel <= 0:
            continue
        total += (2**rel - 1) / math.log2(i + 2)
    return total


def ndcg_at_k(relevance_by_id: Mapping[int, float], ranked_ids: Sequence[int], k: int) -> float:
    """NDCG@k for a ranked caregiver id list against graded relevance labels."""
    if not ranked_ids or k <= 0:
        return 0.0
    gained = [float(relevance_by_id.get(cid, 0.0)) for cid in ranked_ids[:k]]
    ideal = sorted(relevance_by_id.values(), reverse=True)[:k]
    denom = dcg_at_k(ideal, k)
    if denom <= 0:
        return 0.0
    return dcg_at_k(gained, k) / denom


def average_precision(relevance_by_id: Mapping[int, float], ranked_ids: Sequence[int]) -> float:
    """Mean average precision for binary relevance (weight > 0)."""
    hits = 0
    precision_sum = 0.0
    positives = sum(1 for v in relevance_by_id.values() if v > 0)
    if positives == 0:
        return 0.0
    for i, cid in enumerate(ranked_ids, start=1):
        if relevance_by_id.get(cid, 0.0) <= 0:
            continue
        hits += 1
        precision_sum += hits / i
    return precision_sum / positives
