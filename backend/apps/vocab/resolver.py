"""Resolve free-text / multilingual phrases to a canonical condition slug."""

from __future__ import annotations

import re
from functools import lru_cache

from django.db.models import Q

from .models import ConditionTerm
from .seed_data import SEED_CONDITIONS


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


@lru_cache(maxsize=1)
def _seed_index() -> list[tuple[str, str, re.Pattern[str]]]:
    """Fallback index from seed_data when DB is empty (tests / first boot)."""
    rows: list[tuple[str, str, re.Pattern[str]]] = []
    for slug, canonical, synonyms, _ in SEED_CONDITIONS:
        phrases = [canonical, slug.replace("-", " ")]
        for values in synonyms.values():
            phrases.extend(values)
        # Longest phrases first so "blood pressure" wins over "blood"
        phrases = sorted({_norm(p) for p in phrases if p}, key=len, reverse=True)
        for phrase in phrases:
            if not phrase:
                continue
            pattern = re.compile(re.escape(phrase), re.I)
            rows.append((slug, canonical, pattern))
    return rows


def clear_resolver_cache() -> None:
    _seed_index.cache_clear()
    _db_index.cache_clear()


@lru_cache(maxsize=1)
def _db_index() -> list[tuple[str, str, re.Pattern[str]]] | None:
    if not ConditionTerm.objects.filter(active=True).exists():
        return None
    rows: list[tuple[str, str, re.Pattern[str]]] = []
    for term in ConditionTerm.objects.filter(active=True):
        phrases = [_norm(p) for p in term.all_phrases() if p]
        phrases = sorted(set(phrases), key=len, reverse=True)
        for phrase in phrases:
            rows.append((term.slug, term.canonical_en, re.compile(re.escape(phrase), re.I)))
    return rows


def resolve_condition(text: str) -> tuple[str, str]:
    """Return ``(slug, canonical_en)`` or ``("", "")`` if unknown."""
    raw = (text or "").strip()
    if not raw:
        return "", ""

    # Exact slug / canonical match first.
    lowered = _norm(raw)
    try:
        term = ConditionTerm.objects.filter(active=True).filter(
            Q(slug=lowered) | Q(canonical_en__iexact=raw)
        ).first()
        if term:
            return term.slug, term.canonical_en
    except Exception:
        # DB not ready — fall through to seed index.
        pass

    index = _db_index()
    if index is None:
        index = _seed_index()

    for slug, canonical, pattern in index:
        if pattern.search(raw):
            return slug, canonical
    return "", ""


def active_slugs() -> list[str]:
    try:
        slugs = list(
            ConditionTerm.objects.filter(active=True).order_by("slug").values_list("slug", flat=True)
        )
        if slugs:
            return slugs
    except Exception:
        pass
    return [slug for slug, *_ in SEED_CONDITIONS]


def export_vocab_json() -> list[dict]:
    try:
        terms = list(ConditionTerm.objects.filter(active=True).order_by("canonical_en"))
        if terms:
            return [
                {
                    "slug": t.slug,
                    "canonical_en": t.canonical_en,
                    "synonyms": t.synonyms,
                    "version": t.version,
                }
                for t in terms
            ]
    except Exception:
        pass
    return [
        {
            "slug": slug,
            "canonical_en": canonical,
            "synonyms": synonyms,
            "version": 1,
        }
        for slug, canonical, synonyms, _ in SEED_CONDITIONS
    ]
