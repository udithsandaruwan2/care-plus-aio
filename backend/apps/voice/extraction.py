"""Intent extraction — text → structured Care Plus intent.

Two backends behind one ``extract_intent`` function:

* **gemini** — Google Gemini with ``response_mime_type=application/json``
  and a strict schema (used when ``GEMINI_API_KEY`` is set).
* **stub** — deterministic keyword/script heuristics (dev / tests / offline),
  so the pipeline works and is reproducible without any external call.

Both return a dict validated against the model choices:
``{condition, language, languages, care_level, urgency, raw_text, source}``.

``language`` = preferred care language (primary).
``languages`` = all detected in the utterance (supports Sinhala–English /
Tamil–English code-switching).
"""

from __future__ import annotations

import re

from django.conf import settings

from .models import CareLevel, Language, Urgency

# Unicode blocks for script detection.
_SINHALA_RE = re.compile(r"[\u0D80-\u0DFF]")
_TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")
_LATIN_WORD_RE = re.compile(r"[A-Za-z]{2,}")

_LEVEL_MAP: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"දැඩි|බරපතල|advanced|intensive|critical|24\s*hour|specialist", re.I),
        CareLevel.ADVANCED,
    ),
    (re.compile(r"සරල|මූලික|basic|simple|light|companion", re.I), CareLevel.BASIC),
]

_URGENCY_MAP: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"හදිසි|අනතුර|ඉක්මනින්|දැන්ම|emergency|urgent|critical|immediately|asap|soon",
            re.I,
        ),
        Urgency.URGENT,
    ),
]


def detect_languages(text: str) -> list[str]:
    """All languages present in the utterance (script + Latin + explicit names).

    Order is stable: Sinhala → Tamil → English. Empty text → ``[English]``.
    """
    found: set[str] = set()
    if _SINHALA_RE.search(text):
        found.add(Language.SINHALA)
    if _TAMIL_RE.search(text):
        found.add(Language.TAMIL)
    if _LATIN_WORD_RE.search(text):
        found.add(Language.ENGLISH)
    if re.search(r"සිංහල|sinhala", text, re.I):
        found.add(Language.SINHALA)
    if re.search(r"දෙමළ|தமிழ்|tamil", text, re.I):
        found.add(Language.TAMIL)
    if re.search(r"\benglish\b|ඉංග්‍රීසි|ஆங்கிலம்", text, re.I):
        found.add(Language.ENGLISH)
    if not found:
        found.add(Language.ENGLISH)
    order = [Language.SINHALA, Language.TAMIL, Language.ENGLISH]
    return [lang for lang in order if lang in found]


def detect_language(text: str, hint: str | None = None) -> str:
    """Preferred care language for matching (single primary).

    Priority: explicit caregiver-language request → dominant local script →
    soft API hint (only when no local script) → English.
    """
    # Explicit preference in the utterance wins (Singlish/Tanglish included).
    if re.search(r"සිංහල|sinhala", text, re.I):
        return Language.SINHALA
    if re.search(r"දෙමළ|தமிழ்|tamil", text, re.I):
        return Language.TAMIL
    if re.search(r"\benglish\b|ඉංග්‍රීසි|ஆங்கிலம்", text, re.I) and not (
        _SINHALA_RE.search(text) or _TAMIL_RE.search(text)
    ):
        return Language.ENGLISH

    langs = detect_languages(text)
    for preferred in (Language.SINHALA, Language.TAMIL):
        if preferred in langs:
            return preferred

    if hint in Language.values:
        return hint
    return Language.ENGLISH


def _first_match(text: str, table: list[tuple[re.Pattern[str], str]], default: str = "") -> str:
    for pattern, value in table:
        if pattern.search(text):
            return value
    return default


def extract_stub(text: str, hint_language: str | None = None) -> dict:
    from apps.vocab.resolver import resolve_condition

    slug, _canonical = resolve_condition(text)
    languages = detect_languages(text)
    language = detect_language(text, hint_language)
    # Ensure primary is always listed.
    if language not in languages:
        languages = [language, *[lng for lng in languages if lng != language]]
    care_level = _first_match(text, _LEVEL_MAP, default=CareLevel.INTERMEDIATE)
    urgency = _first_match(text, _URGENCY_MAP, default=Urgency.ROUTINE)
    return {
        "condition": slug,
        "language": language,
        "languages": languages,
        "care_level": care_level,
        "urgency": urgency,
        "raw_text": text,
        "source": "stub",
    }


_SCHEMA_HINT = {
    "type": "object",
    "properties": {
        "condition": {"type": "string", "description": "Primary medical condition in English"},
        "language": {
            "type": "string",
            "enum": list(Language.values),
            "description": "Preferred care language for the caregiver",
        },
        "languages": {
            "type": "array",
            "items": {"type": "string", "enum": list(Language.values)},
            "description": "All languages mixed in the utterance (code-switching)",
        },
        "care_level": {"type": "string", "enum": list(CareLevel.values)},
        "urgency": {"type": "string", "enum": list(Urgency.values)},
    },
    "required": ["language", "languages", "care_level", "urgency"],
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
                "utterance. Patients in Sri Lanka often mix Sinhala+English (Singlish) "
                "or Tamil+English (Tanglish) in one sentence — detect ALL languages used "
                "in `languages`, and set `language` to the preferred care language "
                "(usually the local language if present, unless they ask for English). "
                "Return ONLY JSON matching the schema. condition must be a canonical "
                "slug from the Care Plus vocab (e.g. diabetes, dengue) or empty string. "
                "care_level ∈ basic|intermediate|advanced. urgency ∈ routine|urgent|critical."
            ),
        )
        prompt = text
        if hint_language:
            prompt = f"(UI language hint was {hint_language}; prefer auto-detect from text)\n{text}"
        resp = model.generate_content(
            prompt,
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
    raw_langs = data.get("languages") or stub["languages"]
    languages: list[str] = []
    for lng in raw_langs:
        if lng in Language.values and lng not in languages:
            languages.append(lng)
    if language not in languages:
        languages.insert(0, language)
    if not languages:
        languages = stub["languages"]
    care_level = data.get("care_level")
    if care_level not in CareLevel.values:
        care_level = stub["care_level"]
    urgency = data.get("urgency")
    if urgency not in Urgency.values:
        urgency = stub["urgency"]

    from apps.vocab.resolver import resolve_condition

    raw_condition = (data.get("condition") or stub["condition"] or "").strip()
    slug, _ = resolve_condition(raw_condition) if raw_condition else ("", "")
    if not slug and raw_condition:
        # Also try resolving against the full utterance.
        slug, _ = resolve_condition(text)
    if not slug:
        slug = stub["condition"]

    return {
        "condition": slug,
        "language": language,
        "languages": languages,
        "care_level": care_level,
        "urgency": urgency,
        "raw_text": text,
        "source": "gemini",
    }
