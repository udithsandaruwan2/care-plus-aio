"""Conversational turn: ASR → route → Serah reply (+ optional VEHMF match)."""

from __future__ import annotations

import logging
import re
import time

from django.conf import settings

from apps.matching.engine import run_match
from apps.matching.models import CaregiverProfile, MatchResult, MatchRun
from apps.matching.push import push_match_results

from .asr import resolve_transcript
from .backends import extract_intent
from .models import VoiceIntent

logger = logging.getLogger(__name__)

_MATCH_HINT = re.compile(
    r"caregiver|care\s*giver|nurse|find|need|match|කෙනෙක්|ඕන|வேண்டும்|தேவை|diabet|දියවැඩ|நீரிழ|dengue|ඩෙංගු",
    re.I,
)
_REFINE_HINT = re.compile(
    r"closer|nearer|another|different|tamil|sinhala|english|female|male|කිට්ටු|வேறு|மற்றொரு",
    re.I,
)
_CHAT_HINT = re.compile(
    r"^(hi|hello|hey|thanks|thank you|what is|how does|ආයුබෝවන්|வணக்கம்)\b",
    re.I,
)


def _tts_lang(primary: str | None, languages: list[str] | None) -> str:
    langs = languages or []
    if primary == "Tamil" or "Tamil" in langs:
        return "ta-LK"
    if primary == "Sinhala" or "Sinhala" in langs:
        return "si-LK"
    return "en-US"


def _route(text: str, intent: dict, has_prior_match: bool) -> str:
    if has_prior_match and _REFINE_HINT.search(text):
        return "REFINE"
    missing = not (intent.get("condition") and intent.get("language") and intent.get("care_level"))
    if _CHAT_HINT.search(text.strip()) and not _MATCH_HINT.search(text):
        return "CHAT"
    if missing and not _MATCH_HINT.search(text):
        # Short answers during clarify still go CLARIFY.
        return "CLARIFY" if intent.get("condition") or intent.get("language") else "CHAT"
    if missing:
        return "CLARIFY"
    return "MATCH"


def _serah_chat_reply(text: str, lang: str) -> str:
    from apps.common.envutil import refresh_env

    refresh_env()
    backend = (getattr(settings, "DIALOGUE_CHAT_BACKEND", "") or "").strip()
    if not backend:
        backend = "gemini" if settings.GEMINI_API_KEY else "stub"
    if backend == "local":
        return (
            "Local chat model is not configured yet. "
            "I can still help you find a caregiver — tell me the condition and language you need."
        )
    if backend == "gemini" and settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai

            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(settings.GEMINI_MODEL)
            resp = model.generate_content(
                (
                    "You are Serah, Care Plus voice assistant for Sri Lanka. "
                    "Reply in 1–2 short spoken sentences. Be warm. Do NOT diagnose or prescribe. "
                    "If they need a caregiver, invite them to describe condition, language, and care level. "
                    f"Prefer reply language matching BCP-47 {lang}. "
                    f"Patient said: {text}"
                ),
                generation_config={"temperature": 0.4},
            )
            return (resp.text or "").strip() or _stub_chat(text, lang)
        except Exception:
            logger.exception("Serah chat failed")
    return _stub_chat(text, lang)


def _stub_chat(text: str, lang: str) -> str:
    if lang.startswith("si"):
        return (
            "ආයුබෝවන්, මම Serah. ඔබට අවශ්‍ය care ගැන කියන්න — "
            "condition, language, සහ care level."
        )
    if lang.startswith("ta"):
        return (
            "வணக்கம், நான் Serah. உங்களுக்குத் தேவையான பராமரிப்பு பற்றி சொல்லுங்கள் — "
            "நிலை, மொழி, பராமரிப்பு நிலை."
        )
    return (
        "Hi, I’m Serah. Tell me the care you need — condition, preferred language, "
        "and whether you want basic, intermediate, or advanced support."
    )


def _clarify_reply(intent: dict, lang: str) -> str:
    if lang.startswith("si"):
        if not intent.get("condition"):
            return "කුමන රෝගය හෝ රෝග ලක්ෂණය ගැන අවධානය යොමු කරන්නද?"
        if not intent.get("language"):
            return "ඔබේ caregiver කතා කළ යුත්තේ සිංහල, දෙමළ, නැත්නම් ඉංග්‍රීසිද?"
        if not intent.get("care_level"):
            return "කොපමණ සහාය අවශ්‍යද — basic, intermediate, නැත්නම් advanced?"
        return "හොඳ caregiver කෙනෙක් සොයන්න තවත් විස්තර කියන්න."
    if lang.startswith("ta"):
        if not intent.get("condition"):
            return "எந்த நிலை அல்லது அறிகுறியில் கவனம் செலுத்த வேண்டும்?"
        if not intent.get("language"):
            return "உங்கள் பராமரிப்பாளர் சிங்களம், தமிழ் அல்லது ஆங்கிலம் பேச வேண்டுமா?"
        if not intent.get("care_level"):
            return "எவ்வளவு ஆதரவு வேண்டும் — basic, intermediate, அல்லது advanced?"
        return "சரியான பராமரிப்பாளரைக் கண்டுபிடிக்க மேலும் சொல்லுங்கள்."
    if not intent.get("condition"):
        return "What condition or symptom should I focus on?"
    if not intent.get("language"):
        return "Which language should your caregiver speak — Sinhala, Tamil, or English?"
    if not intent.get("care_level"):
        return "How much support do you need — basic, intermediate, or advanced?"
    return "Tell me a bit more so I can find the right caregiver."


def _empty_catch_reply(lang: str, *, had_audio: bool) -> str:
    if lang.startswith("si"):
        if had_audio:
            return "ශබ්දය ඇසුණත් වචන හඳුනාගත්තේ නැහැ — ටිකක් දිගට කතා කරලා නැවත උත්සාහ කරන්න."
        return "මයිකය ඇසුණේ නැහැ — mic එක තියලා පැහැදිලිව කතා කරන්න, නතර වුණාට පස්සේ යවන්න."
    if lang.startswith("ta"):
        if had_audio:
            return "ஒலி கேட்டது, ஆனால் சொற்கள் புரியவில்லை — சற்று நீளமாகப் பேசி மீண்டும் முயலுங்கள்."
        return "மைக் கேட்கவில்லை — மைக்கை அழுத்தித் தெளிவாகப் பேசுங்கள், நிறுத்தியதும் அனுப்பும்."
    if had_audio:
        return "I heard audio but couldn’t understand the words — speak a bit longer and try again."
    return "I didn’t catch any speech — hold the mic, speak clearly, then pause so I can reply."


def _attach_tts(payload: dict, reply: str, reply_lang: str) -> dict:
    from .tts import pack_for_api, synthesize

    tts = synthesize(reply, reply_lang)
    payload.update(pack_for_api(tts))
    return payload


def _match_reply(results: list[dict], lang: str) -> str:
    if not results:
        if lang.startswith("si"):
            return "තවම caregiver කෙනෙක් හොයාගත්තේ නැහැ. language හෝ care level එකතු කරන්න."
        if lang.startswith("ta"):
            return "இன்னும் பராமரிப்பாளர் கிடைக்கவில்லை. மொழி அல்லது பராமரிப்பு நிலையைச் சேர்க்கவும்."
        return "I couldn’t find a caregiver yet. Try adding a language or care level."
    top = results[0]
    name = top.get("display_name") or "a caregiver"
    score = int(round(float(top.get("score") or 0) * 100))
    explanation = (top.get("explanation") or "").strip()
    n = len(results)
    if lang.startswith("si"):
        return f"මට {n} දෙනෙක් හොයාගත්තා. හොඳම match එක {name} (score {score}). {explanation}"
    if lang.startswith("ta"):
        return f"நான் {n} பராமரிப்பாளர்களைக் கண்டேன். சிறந்தது {name} (score {score}). {explanation}"
    return f"I found {n} caregivers. Best match is {name} (score {score}). {explanation}"


def _run_vehmf(user, intent: dict) -> dict:
    emergency = intent.get("urgency") in ("urgent", "critical")
    lon = lat = None
    profile = getattr(user, "patient_profile", None)
    if profile is not None and profile.location is not None:
        lon, lat = profile.location.x, profile.location.y

    t0 = time.perf_counter()
    out = run_match(
        condition=intent.get("condition", ""),
        language=intent.get("language", ""),
        care_level=intent.get("care_level", ""),
        query=intent.get("raw_text", ""),
        patient_id=user.pk,
        longitude=lon,
        latitude=lat,
        top_k=5,
        emergency=emergency,
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)

    run = MatchRun.objects.create(
        user=user,
        query=out.query,
        condition=intent.get("condition", ""),
        language=intent.get("language", ""),
        care_level=intent.get("care_level", ""),
        emergency=out.emergency,
        weights=list(out.weights),
        latency_ms=latency_ms,
    )
    profiles = {
        p.id: p
        for p in CaregiverProfile.objects.filter(
            id__in=[r.caregiver_id for r in out.results]
        ).select_related("user")
    }
    result_rows = []
    for rank, hit in enumerate(out.results, start=1):
        MatchResult.objects.create(
            run=run,
            caregiver_id=hit.caregiver_id,
            rank=rank,
            score=hit.score,
            cbf=hit.cbf,
            cf=hit.cf,
            geo=hit.geo,
            trust=hit.trust,
            explanation=hit.explanation,
            distance_m=hit.distance_m,
        )
        p = profiles.get(hit.caregiver_id)
        result_rows.append(
            {
                "caregiver_id": hit.caregiver_id,
                "rank": rank,
                "score": round(hit.score, 6),
                "breakdown": {
                    "cbf": round(hit.cbf, 6),
                    "cf": round(hit.cf, 6),
                    "geo": round(hit.geo, 6),
                    "trust": round(hit.trust, 6),
                },
                "explanation": hit.explanation,
                "distance_m": None if hit.distance_m is None else round(hit.distance_m, 1),
                "display_name": p.display_name if p else "",
                "specialties": p.specialties if p else [],
                "languages": p.languages if p else [],
                "care_levels": p.care_levels if p else [],
                "trust_score": p.trust_score if p else None,
            }
        )

    payload = {
        "request_id": run.pk,
        "latency_ms": latency_ms,
        "query": out.query,
        "emergency": out.emergency,
        "weights": {
            "cbf": round(out.weights[0], 6),
            "cf": round(out.weights[1], 6),
            "geo": round(out.weights[2], 6),
            "trust": round(out.weights[3], 6),
        },
        "results": result_rows,
    }
    push_match_results(user.pk, payload)
    return payload


def process_turn(
    *,
    user,
    client_text: str = "",
    audio: bytes | None = None,
    content_type: str | None = None,
    has_prior_match: bool = False,
    prior_intent: dict | None = None,
    ui_language: str | None = None,
) -> dict:
    """Full conversational turn used by ``POST /voice/turn/``."""
    ui = ui_language if ui_language in ("Sinhala", "Tamil", "English") else None
    asr = resolve_transcript(
        client_text=client_text,
        audio=audio,
        content_type=content_type,
        ui_language=ui,
    )
    text = asr.text.strip()
    # Picker locks reply language even when ASR/transcript is empty.
    reply_lang = _tts_lang(ui, [ui] if ui else None) if ui else "en-US"
    if not text:
        had_audio = bool(audio)
        reply = _empty_catch_reply(reply_lang, had_audio=had_audio)
        return _attach_tts(
            {
                "route": "CHAT",
                "transcript": "",
                "asr_source": asr.source,
                "asr_language": asr.language_hint or ui or "",
                "asr_language_code": asr.language_code or "",
                "reply": reply,
                "reply_lang": reply_lang,
                "intent": None,
                "match": None,
            },
            reply,
            reply_lang,
        )

    # Merge with prior intent chips (clarify / refine continuity).
    base = dict(prior_intent or {})
    hint = ui or asr.language_hint
    extracted = extract_intent(text, hint)
    for key in ("condition", "language", "languages", "care_level", "urgency", "raw_text", "source"):
        val = extracted.get(key)
        if val not in (None, "", []):
            base[key] = val
    base.setdefault("raw_text", text)

    # UI language picker wins for care language + reply language.
    if ui:
        base["language"] = ui
        langs = list(dict.fromkeys([ui, *(base.get("languages") or []), *(asr.languages or [])]))
        base["languages"] = [x for x in langs if x in ("Sinhala", "Tamil", "English")]
    else:
        asr_langs = [x for x in (asr.languages or []) if x in ("Sinhala", "Tamil", "English")]
        if asr.language_hint in ("Sinhala", "Tamil", "English"):
            if asr.language_hint not in asr_langs:
                asr_langs = [asr.language_hint, *asr_langs]
        if asr_langs:
            merged = list(dict.fromkeys([*asr_langs, *(base.get("languages") or [])]))
            base["languages"] = merged
            if asr.language_hint in ("Sinhala", "Tamil"):
                base["language"] = asr.language_hint
            elif not base.get("language"):
                base["language"] = asr_langs[0]

    route = _route(text, base, has_prior_match)
    reply_lang = _tts_lang(base.get("language"), base.get("languages"))

    match_payload = None
    if route in ("MATCH", "REFINE"):
        VoiceIntent.objects.create(
            user=user,
            raw_text=base.get("raw_text", text),
            condition=base.get("condition", ""),
            language=base.get("language") or "English",
            languages=base.get("languages") or [base.get("language") or "English"],
            care_level=base.get("care_level") or "intermediate",
            urgency=base.get("urgency") or "routine",
            source=base.get("source") or "stub",
        )
        try:
            match_payload = _run_vehmf(user, base)
            reply = _match_reply(match_payload.get("results") or [], reply_lang)
            route = "MATCH"
        except Exception as exc:
            logger.exception("VEHMF in dialogue turn failed")
            reply = f"Matching is briefly unavailable ({exc}). Try again in a moment."
            route = "CHAT"
            match_payload = None
    elif route == "CLARIFY":
        reply = _clarify_reply(base, reply_lang)
    else:
        reply = _serah_chat_reply(text, reply_lang)

    return _attach_tts(
        {
            "route": route,
            "transcript": text,
            "asr_source": asr.source,
            "asr_language": asr.language_hint or ui or "",
            "asr_language_code": asr.language_code or "",
            "reply": reply,
            "reply_lang": reply_lang,
            "intent": {
                "condition": base.get("condition") or "",
                "language": base.get("language") or "",
                "languages": base.get("languages") or [],
                "care_level": base.get("care_level") or "",
                "urgency": base.get("urgency") or "routine",
                "raw_text": base.get("raw_text") or text,
                "source": base.get("source") or asr.source,
            },
            "match": match_payload,
        },
        reply,
        reply_lang,
    )
