"""Conversational turn: ASR → route → Serah reply (+ optional VEHMF match)."""

from __future__ import annotations

import logging
import time

from apps.matching.engine import run_match
from apps.matching.models import CaregiverProfile, MatchResult, MatchRun
from apps.matching.push import push_match_results

from .asr import resolve_transcript
from .backends import extract_intent
from .models import VoiceIntent
from .replies import serah_reply
from .router import classify_turn
from .session import (
    get_or_create_active_session,
    open_questions_for_intent,
    persist_session_after_turn,
)

logger = logging.getLogger(__name__)


def _tts_lang(primary: str | None, languages: list[str] | None) -> str:
    langs = languages or []
    if primary == "Tamil" or "Tamil" in langs:
        return "ta-LK"
    if primary == "Sinhala" or "Sinhala" in langs:
        return "si-LK"
    return "en-US"


def _route(text: str, intent: dict, has_prior_match: bool) -> str:
    """Backward-compatible wrapper used by unit tests."""
    return classify_turn(text, intent, has_prior_match=has_prior_match).route


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
    emergency = intent.get("urgency") in ("urgent", "critical") or intent.get("_emergency")
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
        emergency=bool(emergency),
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


def _match_payload_from_run(run: MatchRun) -> dict:
    rows = []
    for mr in run.results.select_related("caregiver", "caregiver__user").all():
        p = mr.caregiver
        rows.append(
            {
                "caregiver_id": mr.caregiver_id,
                "rank": mr.rank,
                "score": round(mr.score, 6),
                "breakdown": {
                    "cbf": round(mr.cbf, 6),
                    "cf": round(mr.cf, 6),
                    "geo": round(mr.geo, 6),
                    "trust": round(mr.trust, 6),
                },
                "explanation": mr.explanation,
                "distance_m": None if mr.distance_m is None else round(mr.distance_m, 1),
                "display_name": p.display_name if p else "",
                "specialties": p.specialties if p else [],
                "languages": p.languages if p else [],
                "care_levels": p.care_levels if p else [],
                "trust_score": p.trust_score if p else None,
            }
        )
    return {
        "request_id": run.pk,
        "latency_ms": run.latency_ms,
        "query": run.query,
        "emergency": run.emergency,
        "weights": {
            "cbf": round(run.weights[0], 6) if len(run.weights) > 0 else 0,
            "cf": round(run.weights[1], 6) if len(run.weights) > 1 else 0,
            "geo": round(run.weights[2], 6) if len(run.weights) > 2 else 0,
            "trust": round(run.weights[3], 6) if len(run.weights) > 3 else 0,
        },
        "results": rows,
    }


def _latest_match_for_user(user) -> dict | None:
    run = MatchRun.objects.filter(user=user).order_by("-created_at").first()
    if not run:
        return None
    return _match_payload_from_run(run)


def process_turn(
    *,
    user,
    client_text: str = "",
    audio: bytes | None = None,
    content_type: str | None = None,
    has_prior_match: bool = False,
    prior_intent: dict | None = None,
    prior_match: dict | None = None,
    ui_language: str | None = None,
) -> dict:
    """Full conversational turn used by ``POST /voice/turn/``."""
    ui = ui_language if ui_language in ("Sinhala", "Tamil", "English") else None
    session = get_or_create_active_session(user, lang=ui or "")

    asr = resolve_transcript(
        client_text=client_text,
        audio=audio,
        content_type=content_type,
        ui_language=ui,
    )
    text = asr.text.strip()
    reply_lang = _tts_lang(ui, [ui] if ui else None) if ui else "en-US"
    if not text:
        had_audio = bool(audio)
        reply = _empty_catch_reply(reply_lang, had_audio=had_audio)
        return _attach_tts(
            {
                "route": "CHAT",
                "situation": "empty",
                "transcript": "",
                "asr_source": asr.source,
                "asr_language": asr.language_hint or ui or "",
                "asr_language_code": asr.language_code or "",
                "reply": reply,
                "reply_lang": reply_lang,
                "intent": None,
                "match": None,
                "clear_match": False,
                "session_id": session.pk,
            },
            reply,
            reply_lang,
        )

    # Session chips → client prior → this turn's extraction (clarify / refine continuity).
    base: dict = dict(session.intent_chips or {})
    if prior_intent:
        for key, val in prior_intent.items():
            if val not in (None, "", []):
                base[key] = val
    hint = ui or asr.language_hint
    extracted = extract_intent(text, hint)
    for key in ("condition", "language", "languages", "care_level", "urgency", "raw_text", "source"):
        val = extracted.get(key)
        if val not in (None, "", []):
            base[key] = val
    base.setdefault("raw_text", text)

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

    session_has_match = session.last_match_run_id is not None
    effective_prior = bool(has_prior_match or session_has_match or prior_match)
    decision = classify_turn(text, base, has_prior_match=effective_prior)
    route = decision.route
    situation = decision.situation
    reply_lang = _tts_lang(base.get("language") or ui, base.get("languages"))

    # Prefer this session's MatchRun, then client prior, then latest run.
    context_match = None
    if session.last_match_run_id:
        run = session.last_match_run
        if run is None:
            run = MatchRun.objects.filter(pk=session.last_match_run_id).first()
        if run is not None:
            context_match = _match_payload_from_run(run)
    if context_match is None and isinstance(prior_match, dict):
        context_match = prior_match
    if effective_prior and context_match is None:
        context_match = _latest_match_for_user(user)

    match_payload = None
    if route == "EMERGENCY":
        base["_emergency"] = True
        base["urgency"] = "urgent"
        if base.get("condition") and base.get("language") and base.get("care_level"):
            try:
                match_payload = _run_vehmf(user, base)
                reply = _match_reply(match_payload.get("results") or [], reply_lang)
                route = "MATCH"
                situation = "emergency_match"
            except Exception as exc:
                logger.exception("Emergency VEHMF failed")
                reply = serah_reply(
                    text=text,
                    lang=reply_lang,
                    situation="emergency",
                    has_prior_match=effective_prior,
                )
                reply = f"{reply} (Matching briefly unavailable: {exc})"
                route = "CHAT"
        else:
            reply = serah_reply(
                text=text,
                lang=reply_lang,
                situation="emergency",
                has_prior_match=effective_prior,
            )
            route = "CHAT"
    elif route in ("MATCH", "REFINE"):
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
            situation = "match_error"
            match_payload = None
    elif route == "CLARIFY":
        reply = _clarify_reply(base, reply_lang)
    elif route == "ACTION":
        reply = serah_reply(
            text=text,
            lang=reply_lang,
            situation="request",
            has_prior_match=True,
            match=context_match,
        )
        match_payload = None
    else:
        reply = serah_reply(
            text=text,
            lang=reply_lang,
            situation=situation,
            has_prior_match=effective_prior,
            match=context_match,
        )

    intent_out = {
        "condition": base.get("condition") or "",
        "language": base.get("language") or "",
        "languages": base.get("languages") or [],
        "care_level": base.get("care_level") or "",
        "urgency": base.get("urgency") or "routine",
        "raw_text": base.get("raw_text") or text,
        "source": base.get("source") or asr.source,
    }
    match_run_id = None
    if match_payload and match_payload.get("request_id"):
        match_run_id = int(match_payload["request_id"])

    persist_session_after_turn(
        session,
        intent=intent_out,
        route=route,
        situation=situation,
        user_text=text,
        reply=reply,
        match_run_id=match_run_id,
        clear_match=decision.clear_match,
    )

    return _attach_tts(
        {
            "route": route,
            "situation": situation,
            "transcript": text,
            "asr_source": asr.source,
            "asr_language": asr.language_hint or ui or "",
            "asr_language_code": asr.language_code or "",
            "reply": reply,
            "reply_lang": reply_lang,
            "intent": intent_out,
            "match": match_payload,
            "clear_match": decision.clear_match,
            "session_id": session.pk,
            "open_questions": open_questions_for_intent(intent_out),
        },
        reply,
        reply_lang,
    )
