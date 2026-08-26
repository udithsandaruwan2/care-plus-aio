"""Structured voice actions for the Serah client executor.

The dialogue turn returns ``action: { type, caregiver_id?, rank?, name_query?,
package_id?, days?, addon_query? }`` so the web client can open a profile,
describe a caregiver, enqueue a care request, or drive package checkout
without parsing free-text replies alone.
"""

from __future__ import annotations

import re
from typing import Any


ACTION_SITUATIONS = frozenset(
    {
        "request",
        "view_profile",
        "describe_caregiver",
        "request_status",
        "select_package",
        "confirm_checkout",
        "cancel_flow",
    }
)

_ORDINAL = {
    "first": 1,
    "1st": 1,
    "top": 1,
    "one": 1,
    "second": 2,
    "2nd": 2,
    "two": 2,
    "third": 3,
    "3rd": 3,
    "three": 3,
    "fourth": 4,
    "4th": 4,
    "four": 4,
    "fifth": 5,
    "5th": 5,
    "five": 5,
}

_RANK_NUM = re.compile(
    r"(?:#|number|no\.?|rank)\s*(\d+)\b|"
    r"(?:#|number|no\.?|rank)\s+"
    r"(first|1st|top|one|second|2nd|two|third|3rd|three|fourth|4th|four|fifth|5th|five)\b|"
    r"\b(?:the\s+)?"
    r"(first|1st|top|second|2nd|third|3rd|fourth|4th|fifth|5th)\b",
    re.I,
)

_STRIP_FOR_NAME = re.compile(
    r"\b("
    r"please|thanks|thank\s*you|"
    r"review|check|open|show|see|look\s*at|read|"
    r"his|her|their|the|a|an|this|that|"
    r"profile|details?|bio|caregiver|nurse|carer|"
    r"request|book|hire|send|choose|select|want|"
    r"tell\s*me\s*more|describe|about|"
    r"number|rank|first|second|third|fourth|fifth|top|1st|2nd|3rd|4th|5th"
    r")\b|[^\w\s'-]",
    re.I,
)

_PACKAGE_HINT = re.compile(
    r"\b("
    r"basic(\s+home)?(\s+care)?|"
    r"intermediate(\s+nursing)?|"
    r"advanced(\s+clinical)?(\s+care)?|"
    r"night\s+respite(\s+care)?|"
    r"pediatric(\s+home)?(\s+support)?|"
    r"palliative(\s+comfort)?(\s+care)?|"
    r"post[\s-]*surgery(\s+recovery)?|"
    r"standard(\s+(package|plan|care))?"
    r")\b",
    re.I,
)

_ADDON_HINT = re.compile(
    r"\b("
    r"meals?|meal\s+support|food|"
    r"hospital\s+escort|escort|"
    r"clinic\s+transport|transport|"
    r"care\s+supplies(\s+kit)?|supplies|"
    r"physiotherapy(\s+visit)?|physio|"
    r"overnight(\s+watch)?"
    r")\b",
    re.I,
)

_STRIP_FOR_PACKAGE = re.compile(
    r"\b("
    r"please|thanks|thank\s*you|"
    r"select|choose|pick|take|want|get|"
    r"the|a|an|this|that|"
    r"package|plan|option|care|"
    r"for|with|and|plus|add|include|including|"
    r"days?|week|fortnight|month|"
    r"number|rank|first|second|third|fourth|fifth|top|1st|2nd|3rd|4th|5th|"
    r"\d+"
    r")\b|[^\w\s'-]",
    re.I,
)


def parse_rank(text: str) -> int | None:
    raw = (text or "").strip()
    if not raw:
        return None
    m = _RANK_NUM.search(raw)
    if not m:
        return None
    if m.group(1):
        try:
            n = int(m.group(1))
        except ValueError:
            return None
        return n if n >= 1 else None
    key = (m.group(2) or m.group(3) or "").lower()
    return _ORDINAL.get(key)


def parse_name_query(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    cleaned = _STRIP_FOR_NAME.sub(" ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -'")
    # Ignore short noise / bare affirmations.
    if len(cleaned) < 2:
        return ""
    if cleaned.lower() in {"yes", "yeah", "yep", "ok", "okay", "sure", "him", "her", "them"}:
        return ""
    return cleaned


def parse_days(text: str) -> int | None:
    raw = (text or "").strip().lower()
    if not raw:
        return None
    m = re.search(r"\b(\d{1,3})\s*(?:day|days)\b", raw)
    if m:
        try:
            n = int(m.group(1))
        except ValueError:
            return None
        return n if 1 <= n <= 365 else None
    if re.search(r"\b(a\s+)?week\b|\bseven\s+days\b", raw):
        return 7
    if re.search(r"\b(a\s+)?fortnight\b|\btwo\s+weeks?\b", raw):
        return 14
    if re.search(r"\b(a\s+)?month\b|\bthirty\s+days\b", raw):
        return 30
    if re.search(r"\bfive\s+days\b", raw):
        return 5
    if re.search(r"\bten\s+days\b", raw):
        return 10
    return None


def parse_package_query(text: str) -> str:
    """Spoken package hint (name / level) for the client catalog resolver."""
    raw = (text or "").strip()
    if not raw:
        return ""
    m = _PACKAGE_HINT.search(raw)
    if m:
        return re.sub(r"\s+", " ", m.group(0)).strip()
    cleaned = _STRIP_FOR_PACKAGE.sub(" ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -'")
    if len(cleaned) < 2:
        return ""
    if cleaned.lower() in {"yes", "yeah", "yep", "ok", "okay", "sure"}:
        return ""
    return cleaned


def parse_addon_query(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    hits = [m.group(0) for m in _ADDON_HINT.finditer(raw)]
    if not hits:
        return ""
    return " ".join(dict.fromkeys(h.lower() for h in hits))


def _norm_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def resolve_hit(
    results: list[dict[str, Any]],
    *,
    caregiver_id: int | None = None,
    rank: int | None = None,
    name_query: str = "",
) -> dict[str, Any] | None:
    """Map caregiver_id / rank / spoken name → a match result row."""
    rows = [r for r in results if isinstance(r, dict)]
    if not rows:
        return None

    if caregiver_id is not None:
        for row in rows:
            try:
                if int(row.get("caregiver_id")) == int(caregiver_id):
                    return row
            except (TypeError, ValueError):
                continue

    if rank is not None:
        for row in rows:
            try:
                if int(row.get("rank")) == int(rank):
                    return row
            except (TypeError, ValueError):
                continue

    q = _norm_name(name_query)
    if q:
        # Exact / substring on display_name, then token overlap.
        best: dict[str, Any] | None = None
        best_score = 0.0
        q_tokens = {t for t in q.split() if len(t) > 1}
        for row in rows:
            name = _norm_name(str(row.get("display_name") or ""))
            if not name:
                continue
            if name == q or q in name or name in q:
                return row
            name_tokens = {t for t in name.split() if len(t) > 1}
            if not q_tokens or not name_tokens:
                continue
            overlap = len(q_tokens & name_tokens) / len(q_tokens)
            if overlap > best_score and overlap >= 0.5:
                best_score = overlap
                best = row
        if best is not None:
            return best

    return None


def build_voice_action(
    situation: str,
    text: str,
    match: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Build a client-executable action for ACTION (and related) situations."""
    if situation not in ACTION_SITUATIONS:
        return None

    results = []
    if isinstance(match, dict):
        raw = match.get("results") or []
        if isinstance(raw, list):
            results = [r for r in raw if isinstance(r, dict)]

    rank = parse_rank(text)
    name_query = parse_name_query(text)
    days = parse_days(text)
    package_query = parse_package_query(text)
    addon_query = parse_addon_query(text)

    action: dict[str, Any] = {"type": situation}

    if situation in {"select_package", "confirm_checkout"}:
        if package_query:
            action["package_id"] = package_query
            action["name_query"] = package_query
        elif name_query:
            action["name_query"] = name_query
        if rank is not None:
            action["rank"] = rank
        if days is not None:
            action["days"] = days
        if addon_query:
            action["addon_query"] = addon_query
        action.setdefault("package_id", None)
        action.setdefault("days", days)
        action.setdefault("addon_ids", [])
        return action

    hit = resolve_hit(results, rank=rank, name_query=name_query)
    # Default to top match when the user did not specify who.
    if hit is None and results and not name_query and rank is None:
        hit = results[0]

    if hit is not None:
        try:
            action["caregiver_id"] = int(hit["caregiver_id"])
        except (KeyError, TypeError, ValueError):
            pass
        try:
            action["rank"] = int(hit.get("rank") or rank or 0) or None
        except (TypeError, ValueError):
            if rank is not None:
                action["rank"] = rank
    elif rank is not None:
        action["rank"] = rank
    if name_query:
        action["name_query"] = name_query
    action.setdefault("package_id", None)
    action.setdefault("days", None)
    action.setdefault("addon_ids", [])
    return action


def last_serah_text(history: list | None) -> str:
    for turn in reversed(history or []):
        if not isinstance(turn, dict):
            continue
        if turn.get("role") == "serah":
            return str(turn.get("text") or "").strip()
    return ""
