"""Intent extraction — text → structured Care Plus intent.

Two backends behind one ``extract_intent`` function:

* **gemini** — Google Gemini 1.5 Flash with ``response_mime_type=application/json``
  and a strict schema (used when ``GEMINI_API_KEY`` is set).
* **stub** — deterministic keyword/script heuristics (dev / tests / offline),
  so the pipeline works and is reproducible without any external call.

Both return a dict validated against the model choices:
``{condition, language, care_level, urgency, raw_text, source}``.
"""

from __future__ import annotations

import re

from django.conf import settings

from .models import CareLevel, Language, Urgency

# Unicode blocks for script detection.
_SINHALA_RE = re.compile(r"[\u0D80-\u0DFF]")
_TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")

# condition keywords → canonical English label (Sinhala/Tamil/English).
_CONDITION_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"දියවැඩ|நீரிழ|diabet", re.I), "Diabetes"),
    (
        re.compile(r"අධි\s*රුධිර|රුධිර\s*පීඩ|இரத்த\s*அழுத்த|hypertens|blood\s*pressure", re.I),
        "Hypertension",
    ),
    (re.compile(r"හෘද|இதய|cardiac|heart", re.I), "Cardiac"),
    (re.compile(r"ඇදුම|ஆஸ்துமா|asthma", re.I), "Asthma"),
    (re.compile(r"ආඝාත|stroke|paralys", re.I), "Stroke"),
    (re.compile(r"පිළිකා|புற்றுநோய்|cancer", re.I), "Cancer"),
    (re.compile(r"වයෝවෘද්ධ|elderly|geriatric|වැඩිහිටි", re.I), "Elderly care"),
]

_LEVEL_MAP: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"දැඩි|බරපතල|advanced|intensive|critical|24\s*hour|specialist", re.I),
        CareLevel.ADVANCED,
    ),
    (re.compile(r"සරල|මූලික|basic|simple|light|companion", re.I), CareLevel.BASIC),
]

_URGENCY_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"හදිසි|අනතුර|emergency|urgent|critical|දැන්ම|immediately", re.I), Urgency.URGENT),
]


def detect_language(text: str, hint: str | None = None) -> str:
    if hint in Language.values:
        return hint
    if _SINHALA_RE.search(text):
        return Language.SINHALA
    if _TAMIL_RE.search(text):
        return Language.TAMIL
    # Explicit language mentions.
    if re.search(r"සිංහල|sinhala", text, re.I):
        return Language.SINHALA
    if re.search(r"දෙමළ|தமிழ்|tamil", text, re.I):
        return Language.TAMIL
    return Language.ENGLISH


def _first_match(text: str, table: list[tuple[re.Pattern[str], str]], default: str = "") -> str:
    for pattern, value in table:
        if pattern.search(text):
            return value
    return default


def extract_stub(text: str, hint_language: str | None = None) -> dict:
    condition = _first_match(text, _CONDITION_MAP, default="")
    language = detect_language(text, hint_language)
    care_level = _first_match(text, _LEVEL_MAP, default=CareLevel.INTERMEDIATE)
    urgency = _first_match(text, _URGENCY_MAP, default=Urgency.ROUTINE)
    return {
        "condition": condition,
        "language": language,
        "care_level": care_level,
        "urgency": urgency,
        "raw_text": text,
        "source": "stub",
    }


_SCHEMA_HINT = {
    "type": "object",
    "properties": {
        "condition": {"type": "string", "description": "Primary medical condition in English"},
        "language": {"type": "string", "enum": list(Language.values)},
        "care_level": {"type": "string", "enum": list(CareLevel.values)},
        "urgency": {"type": "string", "enum": list(Urgency.values)},
    },
    "required": ["language", "care_level", "urgency"],
}


def extract_gemini(text: str, hint_language: str | None = None) -> dict:
    """Call Gemini with structured JSON output; fall back to stub on any error."""
    try:
        import google.generativeai as genai  # lazy import; optional dependency
    except ImportError:
        return extract_stub(text, hint_language)

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            settings.GEMINI_MODEL,
            system_instruction=(
                "You extract structured caregiver-matching intent from a patient's "
                "utterance (Sinhala, Tamil, or English). Return ONLY JSON matching the "
                "schema. condition must be an English medical label (or empty). "
                "care_level ∈ basic|intermediate|advanced. urgency ∈ routine|urgent|critical."
            ),
        )
        resp = model.generate_content(
            text,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": _SCHEMA_HINT,
                "temperature": 0.0,
            },
        )
        import json

        data = json.loads(resp.text)
    except Exception:
        return extract_stub(text, hint_language)

    # Normalize + validate against choices; fall back per-field.
    stub = extract_stub(text, hint_language)
    language = data.get("language")
    if language not in Language.values:
        language = stub["language"]
    care_level = data.get("care_level")
    if care_level not in CareLevel.values:
        care_level = stub["care_level"]
    urgency = data.get("urgency")
    if urgency not in Urgency.values:
        urgency = stub["urgency"]
    return {
        "condition": (data.get("condition") or stub["condition"]).strip(),
        "language": language,
        "care_level": care_level,
        "urgency": urgency,
        "raw_text": text,
        "source": "gemini",
    }


def extract_intent(text: str, hint_language: str | None = None) -> dict:
    backend = getattr(settings, "VOICE_INTENT_BACKEND", "stub")
    if backend == "gemini" and settings.GEMINI_API_KEY:
        return extract_gemini(text, hint_language)
    return extract_stub(text, hint_language)
