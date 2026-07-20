"""Localized VEHMF explanations and match copy (Sinhala / Tamil / English)."""

from __future__ import annotations

# contributor index → localized reason phrase (without "Matched because" wrapper)
XAI_REASONS: dict[int, dict[str, str]] = {
    0: {
        "en": "strong medical/skill match",
        "si": "වෛද්‍ය හා කුසලතා ගැලපීම ඉතා හොඳයි",
        "ta": "மருத்துவ/திறன் பொருத்தம் வலுவானது",
    },
    1: {
        "en": "highly rated by similar patients",
        "si": "සමාන රෝගීන්ගෙන් ඉහළ ශ්‍රේණිගත කිරීමක් ලැබී ඇත",
        "ta": "ஒத்த நோயாளிகளால் உயர் மதிப்பீடு",
    },
    2: {
        "en": "very close / short travel time",
        "si": "ඔබට ඉතා ආසන්න / ගමන් කාලය අඩුයි",
        "ta": "மிக அருகில் / குறுகிய பயண நேரம்",
    },
    3: {
        "en": "high trust & completion record",
        "si": "විශ්වාසය සහ සේවා සම්පූර්ණතාව ඉහළයි",
        "ta": "நம்பிக்கை மற்றும் பூர்த்தி பதிவு உயர்ந்தது",
    },
}

_EN_REASON_TO_IDX = {v["en"]: k for k, v in XAI_REASONS.items()}


def lang_key(lang: str) -> str:
    """Map BCP-47 or display name → en|si|ta."""
    if not lang:
        return "en"
    low = lang.lower()
    if low.startswith("si") or low == "sinhala":
        return "si"
    if low.startswith("ta") or low == "tamil":
        return "ta"
    return "en"


def xai_reason(contributor: int, lang: str) -> str:
    return XAI_REASONS.get(contributor, XAI_REASONS[0])[lang_key(lang)]


def format_match_explanation(contributor: int, lang: str) -> str:
    """Full XAI sentence for a contributor index."""
    lk = lang_key(lang)
    reason = xai_reason(contributor, lang)
    if lk == "si":
        return f"ගැලපෙන්නේ මෙම නිසාවෙන්: {reason}."
    if lk == "ta":
        return f"பொருந்துவதற்கான காரணம்: {reason}."
    return f"Matched because: {reason}."


def localize_explanation(stored: str, lang: str) -> str:
    """Translate stored English explanation for spoken/UI copy."""
    lk = lang_key(lang)
    if lk == "en" or not stored:
        return stored
    text = stored.strip()
    prefix = "Matched because: "
    if text.startswith(prefix):
        reason = text[len(prefix) :].rstrip(".").strip()
        idx = _EN_REASON_TO_IDX.get(reason)
        if idx is not None:
            return format_match_explanation(idx, lang)
    for idx, reasons in XAI_REASONS.items():
        if reasons["en"] in text:
            return format_match_explanation(idx, lang)
    return stored


def match_spoken_reply(
    results: list[dict],
    lang: str,
    *,
    refined: bool = False,
    deltas: dict | None = None,
) -> str:
    """Serah's spoken/written line after VEHMF returns caregivers."""
    lk = lang_key(lang)
    if not results:
        if lk == "si":
            return (
                "තවම සුදුසු පරිචාරකයෙක් හොයාගත්තේ නැහැ. "
                "භාෂාව හෝ සැලකිය යුතු සේවා මට්ටම එකතු කරලා නැවත කියන්න."
            )
        if lk == "ta":
            return (
                "இன்னும் பொருத்தமான பராமரிப்பாளர் கிடைக்கவில்லை. "
                "மொழி அல்லது பராமரிப்பு நிலையைச் சேர்த்து மீண்டும் சொல்லுங்கள்."
            )
        return "I couldn’t find a caregiver yet. Try adding a language or care level."

    top = results[0]
    name = top.get("display_name") or ("පරිචාරකයෙක්" if lk == "si" else "பராமரிப்பாளர்" if lk == "ta" else "a caregiver")
    score = int(round(float(top.get("score") or 0) * 100))
    explanation = localize_explanation((top.get("explanation") or "").strip(), lang)
    n = len(results)

    refine_bits: list[str] = []
    if deltas:
        if deltas.get("language"):
            refine_bits.append(str(deltas["language"]))
        if deltas.get("max_distance_km") is not None:
            km = deltas["max_distance_km"]
            if lk == "si":
                refine_bits.append(f"කි.මී. {km:g} ඇතුළත")
            elif lk == "ta":
                refine_bits.append(f"{km:g} km உள்ளே")
            else:
                refine_bits.append(f"within {km:g} km")
        if deltas.get("specialty"):
            refine_bits.append(str(deltas["specialty"]))
        if deltas.get("care_level"):
            refine_bits.append(str(deltas["care_level"]))
    filter_note = ", ".join(refine_bits)

    if refined and filter_note:
        if lk == "si":
            return (
                f"ඔබ කිව්වා දැන් යාවත්කාලීන කළා ({filter_note}). "
                f"දැන් {n} දෙනෙක් — හොඳම තේරීම {name}, ගැලපුම් ලකුණු {score}%. {explanation}"
            )
        if lk == "ta":
            return (
                f"நீங்கள் சொன்னபடி புதுப்பித்தேன் ({filter_note}). "
                f"இப்போது {n} பேர் — சிறந்தது {name}, பொருத்த மதிப்பு {score}%. {explanation}"
            )
        return (
            f"Updated shortlist ({filter_note}). Now {n} caregivers — best is {name} "
            f"(score {score}%). {explanation}"
        )

    if lk == "si":
        return (
            f"මට සුදුසු පරිචාරකයින් {n} දෙනෙක් හොයාගත්තා. "
            f"හොඳම තේරීම {name} — ගැලපුම් ලකුණු {score}%. {explanation}"
        )
    if lk == "ta":
        return (
            f"உங்களுக்கு ஏற்ற பராமரிப்பாளர்கள் {n} பேரைக் கண்டேன். "
            f"சிறந்தது {name} — பொருத்த மதிப்பு {score}%. {explanation}"
        )
    return f"I found {n} caregivers. Best match is {name} (score {score}%). {explanation}"
