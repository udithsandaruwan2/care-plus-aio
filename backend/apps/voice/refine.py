"""Parse post-match refine utterances into filter deltas (Step 15i)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

_LANG = re.compile(
    r"(?:\bonly\s+)?\b(tamil|sinhala|english)\b(?:\s+only|\s+speakers?)?",
    re.I,
)
_DISTANCE_KM = re.compile(
    r"(?:within|under|less\s+than|inside|max(?:imum)?)\s*(\d+(?:\.\d+)?)\s*(?:km|kilometers?|kilometres?)|"
    r"(\d+(?:\.\d+)?)\s*(?:km|kilometers?|kilometres?)\s*(?:or\s*less|radius|max)?|"
    r"කි\.?මී\.?\s*(\d+)|(\d+)\s*කි\.?මී",
    re.I,
)
_CLOSER = re.compile(r"\b(closer|nearer|nearby|near\s+me|short(?:er)?\s+distance)\b|කිට්ටු|ලංකට|அருகில்", re.I)
_CARE = re.compile(
    r"\b(advanced|intermediate|basic)(?:\s+only)?\b|"
    r"more\s+experienced|higher\s+care",
    re.I,
)
_SPECIALTY = re.compile(
    r"\b(diabetes|dengue|hypertension|asthma|dementia|wound\s*care|elderly\s*care|"
    r"stroke|cancer|palliative|maternity|pediatric|paediatric)\b",
    re.I,
)

_LANG_MAP = {
    "tamil": "Tamil",
    "sinhala": "Sinhala",
    "english": "English",
}

_CARE_MAP = {
    "advanced": "advanced",
    "intermediate": "intermediate",
    "basic": "basic",
    "more experienced": "advanced",
    "higher care": "advanced",
}

# Soft radius when user says "closer" without an explicit km.
_DEFAULT_CLOSER_KM = 15.0


@dataclass(frozen=True)
class RefineDeltas:
    language: str | None = None
    care_level: str | None = None
    specialty: str | None = None
    max_distance_km: float | None = None
    prefer_closer: bool = False

    def applied(self) -> bool:
        return bool(
            self.language
            or self.care_level
            or self.specialty
            or self.max_distance_km is not None
            or self.prefer_closer
        )

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v not in (None, False)}


def parse_refine_deltas(text: str) -> RefineDeltas:
    """Extract language / care_level / specialty / distance filters from refine speech."""
    raw = (text or "").strip()
    if not raw:
        return RefineDeltas()

    language = None
    m = _LANG.search(raw)
    if m:
        language = _LANG_MAP.get(m.group(1).lower())

    care_level = None
    m = _CARE.search(raw)
    if m:
        token = re.sub(r"\s+", " ", m.group(0).lower()).strip()
        if token.startswith("more") or token.startswith("higher"):
            care_level = "advanced"
        else:
            care_level = _CARE_MAP.get(token.split()[0], token.split()[0])

    specialty = None
    m = _SPECIALTY.search(raw)
    if m:
        specialty = re.sub(r"\s+", " ", m.group(0).lower()).strip()

    max_distance_km = None
    m = _DISTANCE_KM.search(raw)
    if m:
        for g in m.groups():
            if g is not None:
                try:
                    max_distance_km = float(g)
                    break
                except ValueError:
                    pass

    prefer_closer = bool(_CLOSER.search(raw))
    if prefer_closer and max_distance_km is None:
        max_distance_km = _DEFAULT_CLOSER_KM

    return RefineDeltas(
        language=language,
        care_level=care_level,
        specialty=specialty,
        max_distance_km=max_distance_km,
        prefer_closer=prefer_closer,
    )


def apply_deltas_to_intent(intent: dict, deltas: RefineDeltas) -> dict:
    """Mutate a copy of intent chips with refine deltas."""
    out = dict(intent)
    if deltas.language:
        out["language"] = deltas.language
        out["_hard_language"] = True
        langs = list(out.get("languages") or [])
        if deltas.language not in langs:
            langs = [deltas.language, *langs]
        out["languages"] = langs
    if deltas.care_level:
        out["care_level"] = deltas.care_level
        out["_hard_care_level"] = True
    if deltas.specialty:
        # Prefer specialty as condition when refining the shortlist.
        out["condition"] = deltas.specialty
        out["specialty"] = deltas.specialty
    if deltas.max_distance_km is not None:
        out["max_distance_km"] = deltas.max_distance_km
    if deltas.prefer_closer:
        out["prefer_closer"] = True
    return out
