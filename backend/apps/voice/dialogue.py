"""Conversational turn: ASR → route → fast Serah chat or VEHMF match."""

from __future__ import annotations

import logging
import re
import time

from apps.matching.engine import match_run_provenance, run_match
from apps.matching.i18n import localize_explanation, match_spoken_reply
from apps.matching.interactions import record_match_interactions
from apps.matching.models import CaregiverProfile, MatchResult, MatchRun, create_match_run
from apps.matching.push import push_match_results, push_turn_stage

from .actions import build_voice_action, last_serah_text
from .asr import resolve_transcript
from .backends import extract_intent
from .extraction import extract_stub
from .models import create_voice_intent
from .policy import resolve_chat_backend
from .refine import apply_deltas_to_intent, parse_refine_deltas
from .replies import serah_reply
from .router import classify_turn, is_care_seek, needs_slot_extraction
from .session import (
    get_or_create_active_session,
    open_questions_for_intent,
    persist_session_after_turn,
)
from .timings import StageClock, finalize_turn

logger = logging.getLogger(__name__)


def _emit_turn(user, stage: str, **fields) -> None:
    """Best-effort staged push on ``ws/match/<user>/`` (Step 83)."""
    if user is None or not getattr(user, "pk", None):
        return
    from apps.common.observability import request_id_var

    payload = {k: v for k, v in fields.items() if v is not None}
    rid = request_id_var.get()
    if rid:
        payload["request_id"] = rid
    try:
        push_turn_stage(int(user.pk), stage, payload)
    except Exception:
        logger.exception("turn stage push failed stage=%s", stage)


def _serah(
    *,
    user,
    text: str,
    lang: str,
    situation: str,
    has_prior_match: bool = False,
    match: dict | None = None,
    history: list | None = None,
) -> tuple[str, str]:
    line = serah_reply(
        text=text,
        lang=lang,
        situation=situation,
        has_prior_match=has_prior_match,
        match=match,
        history=history,
        user_id=getattr(user, "pk", None),
    )
    return line.text, line.source


def _tts_lang(primary: str | None, languages: list[str] | None) -> str:
    langs = languages or []
    if primary == "Tamil" or "Tamil" in langs:
        return "ta-LK"
    if primary == "Sinhala" or "Sinhala" in langs:
        return "si-LK"
    return "en-US"


def _use_server_voice(reply_lang: str, *, has_match: bool = False) -> bool:
    """Serah always speaks in a neural voice.

    English used to fall through to ``speechSynthesis`` for speed, which meant
    most patients heard the robotic default browser voice. Deferred synthesis
    plus the phrase cache cover the latency, so every line is server audio now;
    ``TTS_BACKEND=browser`` remains the opt-out.
    """
    from django.conf import settings

    backend = (getattr(settings, "TTS_BACKEND", "auto") or "auto").strip().lower()
    return backend not in ("browser", "none", "")


def _route(text: str, intent: dict, has_prior_match: bool) -> str:
    """Backward-compatible wrapper used by unit tests."""
    return classify_turn(text, intent, has_prior_match=has_prior_match).route


def _match_has_results(match: dict | None) -> bool:
    return bool(match and isinstance(match.get("results"), list) and match["results"])


_SEARCH_PROMISE = re.compile(
    r"\b(vehmf|ranking caregivers|finding (your )?(best )?match|"
    r"searching for caregivers|i['’]?m on it|"
    r"let you know.{0,80}(match|result|vehmf|screen)|"
    r"finishes matching|results are ready|"
    r"search going|get that search|let['’]?s (get )?(that )?(search|match)|"
    r"start(ing)? (a |the )?search|looking for (your )?(a )?(caregiver|match)|"
    r"find (you|your) (a )?(caregiver|match))\b",
    re.I,
)

_NO_MATCH_SALVAGE = {
    "thanks",
    "goodbye",
    "cancel",
    "cancel_flow",
    "affirm",
    "about_match",
    "post_match_chat",
    "greeting",
    "smalltalk",
    "faq",
    "request",
    "request_status",
    "view_profile",
    "describe_caregiver",
    "select_package",
    "confirm_checkout",
    "empty",
    "emergency",
}


def _reply_promises_match(reply: str) -> bool:
    return bool(_SEARCH_PROMISE.search(reply or ""))


def _intent_ready_for_match(intent: dict) -> bool:
    if (intent.get("condition") or "").strip():
        return True
    return bool((intent.get("language") or "").strip() and (intent.get("care_level") or "").strip())


def _load_session_match(session) -> dict | None:
    if not session.last_match_run_id:
        return None
    run = session.last_match_run
    if run is None:
        run = MatchRun.objects.filter(pk=session.last_match_run_id).first()
    if run is None:
        return None
    return _match_payload_from_run(run)


def _clarify_reply(intent: dict, lang: str) -> str:
    if lang.startswith("si"):
        if not intent.get("condition"):
            return "කුමන රෝගය හෝ රෝග ලක්ෂණය ගැන අවධානය යොමු කරන්නද?"
        if not intent.get("language"):
            return "ඔබේ caregiver කතා කළ යුත්තේ සිංහල, දෙමළ, නැත්නම් ඉංග්‍රීසිද?"
        if not intent.get("care_level"):
            return "කොපමණ සහාය අවශ්‍යද — මූලික, මධ්‍යම, නැත්නම් උසස්?"
        return "හොඳ caregiver කෙනෙක් සොයන්න තවත් විස්තර කියන්න."
    if lang.startswith("ta"):
        if not intent.get("condition"):
            return "எந்த நிலை அல்லது அறிகுறியில் கவனம் செலுத்த வேண்டும்?"
        if not intent.get("language"):
            return "உங்கள் பராமரிப்பாளர் சிங்களம், தமிழ் அல்லது ஆங்கிலம் பேச வேண்டுமா?"
        if not intent.get("care_level"):
            return "எவ்வளவு ஆதரவு வேண்டும் — அடிப்படை, இடைநிலை, அல்லது மேம்பட்ட?"
        return "சரியான பராமரிப்பாளரைக் கண்டுபிடிக்க மேலும் சொல்லுங்கள்."
    if not intent.get("condition"):
        return "What condition or symptom should I focus on?"
    if not intent.get("language"):
        return "Which language should your caregiver speak — Sinhala, Tamil, or English?"
    if not intent.get("care_level"):
        return "How much support do you need — basic, intermediate, or advanced?"
    return "Tell me a bit more so I can find the right caregiver."


def _attach_tts(
    payload: dict,
    reply: str,
    reply_lang: str,
    *,
    server_voice: bool = True,
    persona: str | None = None,
) -> dict:
    from django.conf import settings

    from .tts import lookup_phrase_cache, pack_for_api, synthesize

    if not server_voice:
        payload.update(
            {
                "reply_audio_base64": "",
                "reply_audio_mime": "",
                "tts_source": "browser",
                "audio_pending": False,
                "tts_cache_hit": False,
            }
        )
        return payload

    cached = lookup_phrase_cache(reply, reply_lang, persona)
    if cached is not None:
        payload.update(pack_for_api(cached))
        payload["audio_pending"] = False
        payload["tts_cache_hit"] = True
        return payload

    # Cache miss: return text immediately; synthesize in background (stream or /voice/tts/).
    if getattr(settings, "TTS_DEFER_UNCACHED", True) and (reply or "").strip():
        payload.update(
            {
                "reply_audio_base64": "",
                "reply_audio_mime": "",
                "tts_source": "pending",
                "audio_pending": True,
                "tts_cache_hit": False,
            }
        )
        return payload

    tts = synthesize(reply, reply_lang, persona)
    payload.update(pack_for_api(tts))
    payload["audio_pending"] = False
    payload["tts_cache_hit"] = False
    return payload


def _match_reply(
    results: list[dict], lang: str, *, refined: bool = False, deltas: dict | None = None
) -> str:
    return match_spoken_reply(results, lang, refined=refined, deltas=deltas)


def _run_vehmf(
    user,
    intent: dict,
    *,
    prior_results: list[dict] | None = None,
    refine: bool = False,
    voice_intent=None,
) -> dict:
    emergency = intent.get("urgency") in ("urgent", "critical") or intent.get("_emergency")
    lon = lat = None
    profile = getattr(user, "patient_profile", None)
    if profile is not None and profile.location is not None:
        lon, lat = profile.location.x, profile.location.y

    max_km = intent.get("max_distance_km")
    try:
        max_km_f = float(max_km) if max_km is not None else None
    except (TypeError, ValueError):
        max_km_f = None

    specialty = (intent.get("specialty") or "").strip()
    prefer_closer = bool(intent.get("prefer_closer"))
    # Hard filters only when refine deltas explicitly asked for them.
    hard_lang = bool(intent.get("_hard_language"))
    hard_care = bool(intent.get("_hard_care_level"))

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
        max_distance_km=max_km_f,
        specialty=specialty,
        prefer_closer=prefer_closer,
        hard_filter_language=hard_lang,
        hard_filter_care_level=hard_care,
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)

    run = create_match_run(
        user=user,
        query=out.query,
        condition=intent.get("condition", ""),
        language=intent.get("language", ""),
        care_level=intent.get("care_level", ""),
        emergency=out.emergency,
        weights=list(out.weights),
        latency_ms=latency_ms,
        source="voice",
        voice_intent=voice_intent,
        **match_run_provenance(out),
    )
    profiles = {
        p.id: p
        for p in CaregiverProfile.objects.filter(
            id__in=[r.caregiver_id for r in out.results]
        ).select_related("user")
    }
    prev_ranks = {
        int(r["caregiver_id"]): int(r["rank"])
        for r in (prior_results or [])
        if r.get("caregiver_id") is not None and r.get("rank") is not None
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
            was_exploratory=bool(getattr(hit, "was_exploratory", False)),
        )
        p = profiles.get(hit.caregiver_id)
        prev = prev_ranks.get(hit.caregiver_id)
        row = {
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
            "was_exploratory": bool(getattr(hit, "was_exploratory", False)),
        }
        if prev is not None:
            row["previous_rank"] = prev
            row["rank_delta"] = prev - rank  # positive = moved up
        result_rows.append(row)

    record_match_interactions(
        user,
        [r.caregiver_id for r in out.results],
        source="voice_match",
    )

    payload = {
        "request_id": run.pk,
        "latency_ms": latency_ms,
        "query": out.query,
        "emergency": out.emergency,
        "cf_enabled": out.cf_enabled,
        "cf_version": out.cf_version,
        "weights": {
            "cbf": round(out.weights[0], 6),
            "cf": round(out.weights[1], 6),
            "geo": round(out.weights[2], 6),
            "trust": round(out.weights[3], 6),
        },
        "results": result_rows,
        "refined": refine,
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
    run = (
        MatchRun.objects.filter(user=user, deleted_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
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
    voice_persona: str | None = None,
) -> dict:
    """Full conversational turn used by ``POST /voice/turn/``."""
    clock = StageClock()
    ui = ui_language if ui_language in ("Sinhala", "Tamil", "English") else None
    session = get_or_create_active_session(user, lang=ui or "")

    with clock.span("asr_ms"):
        asr = resolve_transcript(
            client_text=client_text,
            audio=audio,
            content_type=content_type,
            ui_language=ui,
        )
    text = asr.text.strip()
    _emit_turn(
        user,
        "transcript",
        transcript=text,
        asr_source=asr.source,
        asr_language=asr.language_hint or ui or "",
        asr_language_code=asr.language_code or "",
        session_id=session.pk,
        silent=not bool(text),
    )
    reply_lang = _tts_lang(ui, [ui] if ui else None) if ui else "en-US"
    if not text:
        # Silence / ambient noise is not a turn — keep listening, do not invent a reply.
        payload = {
            "route": "CHAT",
            "situation": "empty",
            "silent": True,
            "transcript": "",
            "asr_source": asr.source,
            "asr_language": asr.language_hint or ui or "",
            "asr_language_code": asr.language_code or "",
            "reply": "",
            "reply_lang": reply_lang,
            "intent": None,
            "match": None,
            "clear_match": False,
            "session_id": session.pk,
            "chat_source": "stub",
            "chat_backend": resolve_chat_backend(),
            "match_engine": "",
        }
        _emit_turn(user, "intent", intent=None, session_id=session.pk)
        _emit_turn(
            user,
            "route",
            route="CHAT",
            situation="empty",
            session_id=session.pk,
        )
        _emit_turn(
            user,
            "reply_text",
            reply="",
            reply_lang=reply_lang,
            route="CHAT",
            situation="empty",
            silent=True,
            session_id=session.pk,
        )
        with clock.span("tts_ms"):
            out = _attach_tts(payload, "", reply_lang, server_voice=False)
        _emit_turn(
            user,
            "reply_audio",
            reply_audio_base64=out.get("reply_audio_base64") or "",
            reply_audio_mime=out.get("reply_audio_mime") or "",
            tts_source=out.get("tts_source"),
            session_id=session.pk,
        )
        _emit_turn(user, "done", situation="empty", silent=True, session_id=session.pk)
        return finalize_turn(
            user,
            out,
            clock.finish(),
            route="CHAT",
            situation="empty",
        )

    # Session chips → client prior → this turn's extraction (clarify / refine continuity).
    base: dict = dict(session.intent_chips or {})
    if prior_intent:
        for key, val in prior_intent.items():
            if val not in (None, "", []):
                base[key] = val
    hint = ui or asr.language_hint
    # Chat stays cheap: local stub slots. Gemini intent only when VEHMF may run.
    with clock.span("intent_ms"):
        if needs_slot_extraction(
            text, has_prior_match=has_prior_match or bool(session.last_match_run_id)
        ):
            extracted = extract_intent(text, hint)
        else:
            extracted = extract_stub(text, hint)
    for key in (
        "condition",
        "language",
        "languages",
        "care_level",
        "urgency",
        "raw_text",
        "source",
        "intent_backend",
        "fallback_reason",
    ):
        val = extracted.get(key)
        if val not in (None, "", []):
            base[key] = val
    base.setdefault("raw_text", text)
    if extracted.get("fallback_reason") is not None and "fallback_reason" not in base:
        base["fallback_reason"] = extracted.get("fallback_reason") or ""
    if extracted.get("intent_backend"):
        base["intent_backend"] = extracted["intent_backend"]

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
    session_match = _load_session_match(session) if session_has_match else None

    visible_match = None
    if _match_has_results(prior_match if isinstance(prior_match, dict) else None):
        visible_match = prior_match
    elif has_prior_match and _match_has_results(session_match):
        visible_match = session_match

    history_match = visible_match
    if history_match is None and _match_has_results(session_match):
        history_match = session_match
    if history_match is None and _match_has_results(
        prior_match if isinstance(prior_match, dict) else None
    ):
        history_match = prior_match

    has_visible_match = _match_has_results(visible_match)
    has_history_match = _match_has_results(history_match)
    effective_prior = has_visible_match

    context_match = visible_match or history_match
    chat_history = list(session.turns or [])[-8:]
    prior_serah = last_serah_text(chat_history)

    with clock.span("route_ms"):
        decision = classify_turn(
            text,
            base,
            has_prior_match=has_visible_match,
            has_history_match=has_history_match,
            last_serah_text=prior_serah,
        )
    route = decision.route
    situation = decision.situation
    # UI picker locks what Serah speaks; caregiver language chips stay on intent.
    if ui:
        reply_lang = _tts_lang(ui, [ui])
    else:
        reply_lang = _tts_lang(base.get("language"), base.get("languages"))

    # Early intent/route for progressive UI (chips + matching state) before VEHMF/TTS.
    intent_preview = {
        "condition": base.get("condition") or "",
        "language": base.get("language") or "",
        "languages": base.get("languages") or [],
        "care_level": base.get("care_level") or "",
        "urgency": base.get("urgency") or "routine",
        "raw_text": base.get("raw_text") or text,
        "source": base.get("source") or asr.source,
        "intent_backend": base.get("intent_backend") or "",
        "fallback_reason": base.get("fallback_reason") or "",
    }
    _emit_turn(user, "intent", intent=intent_preview, session_id=session.pk)
    _emit_turn(
        user,
        "route",
        route=route,
        situation=situation,
        clear_match=decision.clear_match,
        session_id=session.pk,
    )

    match_payload = None
    chat_source = "none"
    action_payload = None
    if route == "EMERGENCY":
        base["_emergency"] = True
        base["urgency"] = "urgent"
        if base.get("condition"):
            try:
                with clock.span("match_ms"):
                    match_payload = _run_vehmf(user, base)
                reply = _match_reply(match_payload.get("results") or [], reply_lang)
                route = "MATCH"
                situation = "emergency_match"
                chat_source = "vehmf"
            except Exception as exc:
                logger.exception("Emergency VEHMF failed")
                with clock.span("chat_ms"):
                    reply, chat_source = _serah(
                        user=user,
                        text=text,
                        lang=reply_lang,
                        situation="emergency",
                        has_prior_match=effective_prior,
                        history=chat_history,
                    )
                reply = f"{reply} (Matching briefly unavailable: {exc})"
                route = "CHAT"
        else:
            with clock.span("chat_ms"):
                reply, chat_source = _serah(
                    user=user,
                    text=text,
                    lang=reply_lang,
                    situation="emergency",
                    has_prior_match=effective_prior,
                    history=chat_history,
                )
            route = "CHAT"
    elif route in ("MATCH", "REFINE"):
        is_refine = route == "REFINE"
        deltas = parse_refine_deltas(text) if is_refine else None
        if deltas and deltas.applied():
            base = apply_deltas_to_intent(base, deltas)
        voice_row = create_voice_intent(
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
            prior_rows = (context_match or {}).get("results") if is_refine else None
            with clock.span("match_ms"):
                match_payload = _run_vehmf(
                    user,
                    base,
                    prior_results=prior_rows if isinstance(prior_rows, list) else None,
                    refine=is_refine,
                    voice_intent=voice_row,
                )
            reply = _match_reply(
                match_payload.get("results") or [],
                reply_lang,
                refined=is_refine,
                deltas=deltas.to_dict() if deltas else None,
            )
            route = "MATCH"
            chat_source = "vehmf"
            if is_refine:
                situation = "refine"
        except Exception as exc:
            logger.exception("VEHMF in dialogue turn failed")
            reply = f"Matching is briefly unavailable ({exc}). Try again in a moment."
            route = "CHAT"
            situation = "match_error"
            match_payload = None
            chat_source = "none"
    elif route == "CLARIFY":
        with clock.span("chat_ms"):
            reply = _clarify_reply(base, reply_lang)
        chat_source = "stub"
    elif route == "ACTION":
        action_match = visible_match or history_match
        action_payload = build_voice_action(situation, text, action_match)
        with clock.span("chat_ms"):
            reply, chat_source = _serah(
                user=user,
                text=text,
                lang=reply_lang,
                situation=situation,
                has_prior_match=has_visible_match,
                match=action_match,
                history=chat_history,
            )
        match_payload = None
    else:
        with clock.span("chat_ms"):
            reply, chat_source = _serah(
                user=user,
                text=text,
                lang=reply_lang,
                situation=situation,
                has_prior_match=effective_prior,
                match=context_match,
                history=chat_history,
            )
        # Gemini sometimes promises VEHMF without the MATCH route. Run it now.
        if situation not in _NO_MATCH_SALVAGE and (
            is_care_seek(text) or _reply_promises_match(reply)
        ):
            if _intent_ready_for_match(base):
                try:
                    with clock.span("match_ms"):
                        match_payload = _run_vehmf(user, base)
                    reply = _match_reply(match_payload.get("results") or [], reply_lang)
                    route = "MATCH"
                    situation = "match"
                    chat_source = "vehmf"
                except Exception as exc:
                    logger.exception("Salvaged VEHMF after chat promise failed")
                    reply = f"Matching is briefly unavailable ({exc}). Try again in a moment."
                    route = "CHAT"
                    situation = "match_error"
                    match_payload = None
                    chat_source = "none"
            else:
                route = "CLARIFY"
                situation = "clarify"
                with clock.span("chat_ms"):
                    reply = _clarify_reply(base, reply_lang)
                chat_source = "stub"

    intent_out = {
        "condition": base.get("condition") or "",
        "language": base.get("language") or "",
        "languages": base.get("languages") or [],
        "care_level": base.get("care_level") or "",
        "urgency": base.get("urgency") or "routine",
        "raw_text": base.get("raw_text") or text,
        "source": base.get("source") or asr.source,
        "intent_backend": base.get("intent_backend") or "",
        "fallback_reason": base.get("fallback_reason") or "",
    }
    # Keep refine filters across turns on the session.
    for key in (
        "specialty",
        "max_distance_km",
        "prefer_closer",
        "_hard_language",
        "_hard_care_level",
    ):
        if key in base and base[key] not in (None, "", False):
            intent_out[key] = base[key]
    match_run_id = None
    if match_payload and match_payload.get("request_id"):
        match_run_id = int(match_payload["request_id"])

    if match_payload and reply_lang:
        for row in match_payload.get("results") or []:
            if isinstance(row, dict) and row.get("explanation"):
                row["explanation"] = localize_explanation(row["explanation"], reply_lang)

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

    open_qs = open_questions_for_intent(intent_out)
    payload = {
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
        "action": action_payload,
        "clear_match": decision.clear_match,
        "session_id": session.pk,
        "open_questions": open_qs,
        "chat_source": chat_source,
        "chat_backend": resolve_chat_backend(),
        "intent_backend": intent_out.get("intent_backend") or "",
        "intent_source": intent_out.get("source") or "",
        "intent_fallback_reason": intent_out.get("fallback_reason") or "",
        "match_engine": "vehmf" if match_payload else "",
    }
    # Re-emit final route/intent if salvage changed them after the early push.
    _emit_turn(user, "intent", intent=intent_out, session_id=session.pk)
    _emit_turn(
        user,
        "route",
        route=route,
        situation=situation,
        clear_match=decision.clear_match,
        session_id=session.pk,
    )
    _emit_turn(
        user,
        "reply_text",
        reply=reply,
        reply_lang=reply_lang,
        route=route,
        situation=situation,
        action=action_payload,
        clear_match=decision.clear_match,
        open_questions=open_qs,
        chat_source=chat_source,
        session_id=session.pk,
    )
    if match_payload is not None:
        _emit_turn(
            user,
            "match",
            match=match_payload,
            route=route,
            situation=situation,
            session_id=session.pk,
        )
    # Reply text is on the wire before TTS starts — time-to-first-text excludes tts_ms.
    clock.mark_first_text()
    with clock.span("tts_ms"):
        out = _attach_tts(
            payload,
            reply,
            reply_lang,
            server_voice=_use_server_voice(reply_lang, has_match=bool(match_payload)),
            persona=voice_persona,
        )
    if not out.get("audio_pending"):
        _emit_turn(
            user,
            "reply_audio",
            reply_audio_base64=out.get("reply_audio_base64") or "",
            reply_audio_mime=out.get("reply_audio_mime") or "",
            tts_source=out.get("tts_source"),
            reply_lang=reply_lang,
            session_id=session.pk,
            tts_cache_hit=out.get("tts_cache_hit"),
        )
    _emit_turn(
        user,
        "done",
        route=route,
        situation=situation,
        session_id=session.pk,
        has_match=bool(match_payload),
        audio_pending=bool(out.get("audio_pending")),
    )
    return finalize_turn(user, out, clock.finish(), route=route, situation=situation)
