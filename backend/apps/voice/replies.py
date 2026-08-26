"""Situation-aware Serah replies (stub + optional rate-limited Gemini chat)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings

from apps.matching.i18n import localize_explanation

from .policy import gemini_chat_allowed, resolve_chat_backend

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SerahLine:
    text: str
    """stub | gemini | local_llm | rate_limited — never used for caregiver ranking."""
    source: str


def _si(lang: str) -> bool:
    return lang.startswith("si")


def _ta(lang: str) -> bool:
    return lang.startswith("ta")


def _display_lang(lang: str) -> str:
    if _si(lang):
        return "Sinhala"
    if _ta(lang):
        return "Tamil"
    return "English"


def stub_for_situation(
    situation: str,
    lang: str,
    *,
    text: str = "",
    match: dict | None = None,
) -> str:
    """Deterministic spoken replies for each conversation situation."""
    from .actions import parse_name_query, parse_rank, resolve_hit

    top = None
    has_results = bool(match and match.get("results"))
    if has_results:
        top = resolve_hit(
            list(match["results"]),
            rank=parse_rank(text),
            name_query=parse_name_query(text),
        ) or match["results"][0]
    name = (top or {}).get("display_name") or ""

    if situation == "thanks":
        if _si(lang):
            return "සාදරයෙන්! තවත් උදව් අවශ්‍ය නම් කතා කරන්න. සුවයක් වේවා."
        if _ta(lang):
            return "மகிழ்ச்சி! மேலும் உதவி வேண்டுமானால் சொல்லுங்கள். நலமாக இருங்கள்."
        return "You’re welcome! I’m here if you need anything else. Take care."

    if situation == "goodbye":
        if _si(lang):
            return "බලමු. මම නිහඬව ඉන්නම් — ආයෙත් අවශ්‍ය නම් Hey Serah කියන්න."
        if _ta(lang):
            return "சந்திப்போம். நான் அமைதியாக இருப்பேன் — தேவைப்பட்டால் Hey Serah என்று சொல்லுங்கள்."
        return "Goodbye — I’ll stay quiet. Say Hey Serah when you want me back."

    if situation == "affirm":
        if _si(lang):
            return "හරි. තවත් යමක් අවශ්‍ය නම් කියන්න — නැත්නම් මේ matches බලන්න."
        if _ta(lang):
            return "சரி. வேறு ஏதேனும் வேண்டுமானால் சொல்லுங்கள் — அல்லது இந்த matches-ஐ பாருங்கள்."
        return "Got it. Say if you need anything else, or browse the matches I found."

    if situation == "greeting":
        if _si(lang):
            return "ආයුබෝවන්, මම Serah. කතා කරන්න — care ප්‍රශ්නයක් හෝ caregiver කෙනෙක් සොයනවා නම් කියන්න."
        if _ta(lang):
            return (
                "வணக்கம், நான் Serah. பேசுங்கள் — பராமரிப்பு கேள்வி அல்லது பராமரிப்பாளர் தேவை என்றால் சொல்லுங்கள்."
            )
        return "Hi, I’m Serah. Talk naturally — ask a care question, or ask me to find a caregiver."

    if situation == "smalltalk":
        if _si(lang):
            return "මම Serah, Care Plus voice assistant. මම caregivers match කරනවා — diagnose කරන්නේ නැහැ."
        if _ta(lang):
            return "நான் Serah, Care Plus உதவியாளர். பராமரிப்பாளர்களைப் பொருத்துகிறேன் — நோய் கண்டறிவதில்லை."
        return "I’m Serah, your Care Plus voice assistant. I match caregivers — I don’t diagnose."

    if situation == "faq":
        if _si(lang):
            return (
                "Care Plus එකේ ඔබේ අවශ්‍යතාව කියන්න — condition, language, care level. "
                "මම VEHMF එකෙන් ranked caregivers පෙන්නනවා."
            )
        if _ta(lang):
            return (
                "Care Plus-இல் உங்கள் தேவையைச் சொல்லுங்கள் — நிலை, மொழி, பராமரிப்பு நிலை. "
                "நான் VEHMF மூலம் ranked பராமரிப்பாளர்களைக் காட்டுவேன்."
            )
        return (
            "Tell me your care need — condition, language, and care level — "
            "and I’ll rank caregivers with VEHMF. You can also just chat with me."
        )

    if situation == "about_match":
        if not has_results:
            if _si(lang):
                return (
                    "දැනට active match list එකක් හමු වුනේ නැහැ. "
                    "නව match එකක් හොයන්න කියන්න, නැත්නම් Browse පිටුවෙන් caregiver තෝරන්න."
                )
            if _ta(lang):
                return (
                    "இப்போது செயல்பாட்டில் உள்ள match பட்டியல் இல்லை. "
                    "புதிய match தேடச் சொல்லலாம், அல்லது Browse பக்கத்தில் பராமரிப்பாளரைத் தேர்வுசெய்யலாம்."
                )
            return (
                "I don’t have an active match list right now. "
                "Ask me to run a new caregiver search, or pick someone from Browse."
            )
        explanation = localize_explanation((top or {}).get("explanation") or "", lang)
        if _si(lang):
            return (
                f"{name or 'ඉහළම තේරීම'} ගැන: {explanation or 'කුසලතා ගැලපීම හොඳයි'}. "
                "වෙනත් කෙනෙක් ඕනේ නම් කියන්න — උදා: ආසන්නයි, දෙමළ පමණි."
            )
        if _ta(lang):
            return (
                f"{name or 'சிறந்த தேர்வு'} பற்றி: {explanation or 'திறன் பொருத்தம் நன்று'}. "
                "வேறு நபர் வேண்டுமானால் சொல்லுங்கள் — எ.கா. அருகில், தமிழ் மட்டும்."
            )
        return (
            f"About {name or 'the top match'}: {explanation or 'strong skill match'}. "
            "Want someone else? Say closer, another, or Tamil only."
        )

    if situation == "request":
        if not has_results:
            if _si(lang):
                return (
                    "දැනට match cards නැහැ. Browse පිටුවෙන් caregiver තෝරන්න, "
                    "නැත්නම් මට අලුත් match එකක් හොයන්න කියන්න."
                )
            if _ta(lang):
                return (
                    "இப்போது match cards இல்லை. Browse பக்கத்தில் ஒரு பராமரிப்பாளரைத் தேர்வுசெய்யுங்கள், "
                    "அல்லது புதிய match தேடச் சொல்லுங்கள்."
                )
            return (
                "I can’t see active match cards right now. "
                "Ask me for a fresh match, or pick someone from Browse."
            )
        if _si(lang):
            return (
                f"{name or 'මේ පරිචාරක'} වෙත care request එක යවනවා. "
                "ඔහු/ඇය පිළිතුරු දෙන තෙක් මොහොතක් ඉන්න."
            )
        if _ta(lang):
            return (
                f"{name or 'இந்த பராமரிப்பாளர்'}-க்கு care request அனுப்புகிறேன். "
                "பதில் வரும் வரை சிறிது காத்திருங்கள்."
            )
        return (
            f"Sending your care request to {name or 'this caregiver'} now. "
            "I’ll let you know when they respond."
        )

    if situation == "view_profile":
        if not has_results:
            if _si(lang):
                return "දැනට match list එකක් නැහැ — පැතිකඩක් විවෘත කරන්න පෙර match එකක් හොයමු."
            if _ta(lang):
                return "இப்போது match பட்டியல் இல்லை — சுயவிவரம் திறக்க முன் ஒரு match தேடுவோம்."
            return "I don’t have a match list yet — let’s find caregivers first, then I can open a profile."
        if _si(lang):
            return f"{name or 'මේ පරිචාරක'}ගේ පැතිකඩ විවෘත කරනවා."
        if _ta(lang):
            return f"{name or 'இந்த பராமரிப்பாளர்'} சுயவிவரத்தைத் திறக்கிறேன்."
        return f"Opening {name or 'this caregiver'}’s profile for you."

    if situation == "describe_caregiver":
        if not has_results:
            if _si(lang):
                return "විස්තර කියන්න match list එකක් ඕනේ — මුලින් caregivers හොයමු."
            if _ta(lang):
                return "விவரம் சொல்ல match பட்டியல் வேண்டும் — முதலில் caregivers தேடுவோம்."
            return "I need a match list before I can describe someone — let’s search first."
        explanation = localize_explanation((top or {}).get("explanation") or "", lang)
        if _si(lang):
            return (
                f"{name or 'ඉහළම තේරීම'}: {explanation or 'කුසලතා ගැලපීම හොඳයි'}. "
                "ඉල්ලීම යවන්න කියන්න, නැත්නම් වෙනත් කෙනෙක් තෝරන්න."
            )
        if _ta(lang):
            return (
                f"{name or 'சிறந்த தேர்வு'}: {explanation or 'திறன் பொருத்தம் நன்று'}. "
                "கோரிக்கை அனுப்பச் சொல்லுங்கள், அல்லது வேறு நபரைத் தேர்வுசெய்யுங்கள்."
            )
        return (
            f"About {name or 'the top match'}: {explanation or 'strong skill match'}. "
            "Say send the request when you’re ready, or pick someone else."
        )

    if situation == "request_status":
        if _si(lang):
            return "මම care request එකේ තත්ත්වය බලනවා."
        if _ta(lang):
            return "கேர் கோரிக்கை நிலையை இப்போது பார்க்கிறேன்."
        return "I’ll check on your care request now."

    if situation == "cancel":
        if _si(lang):
            return "හරි, matching නවත්තුවා. ඕනෑම වෙලාවක ආයෙත් caregiver සොයන්න කියන්න."
        if _ta(lang):
            return "சரி, matching நிறுத்தினேன். வேண்டும்போது மீண்டும் பராமரிப்பாளர் தேடச் சொல்லுங்கள்."
        return "Okay, I won’t keep matching. Say when you want to find a caregiver again."

    if situation == "emergency":
        if _si(lang):
            return (
                "මේක හදිසි වගේ. කරුණාකර 1990 / local emergency services අමතන්න. "
                "මම emergency weights එක්ක caregivers හොයන්නත් පුළුවන්."
            )
        if _ta(lang):
            return (
                "இது அவசரம் போல் தெரிகிறது. தயவுசெய்து 1990 / உள்ளூர் அவசர சேவையை அழையுங்கள். "
                "நான் அவசர weights உடன் பராமரிப்பாளர்களையும் தேடலாம்."
            )
        return (
            "This sounds urgent — please call 1990 or local emergency services. "
            "I can also search caregivers with emergency ranking if you want."
        )

    if situation == "post_match_chat":
        if not has_results:
            if _si(lang):
                return (
                    "ඔබට cards නොපෙනෙනවා නම් ඒක හරි. "
                    "මට අලුත් caregiver match එකක් හොයන්න කියන්න, නැත්නම් Browse එකට යමු."
                )
            if _ta(lang):
                return (
                    "கார்டுகள் தெரியவில்லை என்றால் பரவாயில்லை. "
                    "புதிய caregiver match தேடச் சொல்லலாம், அல்லது Browse-க்கு செல்லலாம்."
                )
            return (
                "If you can’t see caregiver cards right now, that’s okay. "
                "Ask me for a fresh match, or use Browse to pick someone directly."
            )
        if _si(lang):
            return (
                "මම තාම matches පෙන්නලා තියෙනවා. ස්තුති කිව්වොත් හරි — "
                "නැත්නම් closer / another / why number one කියන්න."
            )
        if _ta(lang):
            return (
                "Matches இன்னும் இருக்கின்றன. நன்றி என்றால் பரவாயில்லை — "
                "அல்லது closer / another / why number one என்று சொல்லுங்கள்."
            )
        return (
            "Your matches are still here. You’re welcome to say thanks, ask why #1 ranked high, "
            "or ask for someone closer."
        )

    if situation == "advice":
        if _si(lang):
            return (
                "මම වෛද්‍ය diagnose කරන්නේ නැහැ — සාමාන්‍ය උපදෙස් විතරයි. "
                "බරපතල නම් doctor එක්ක කතා කරන්න. caregiver ඕනේ නම් කියන්න."
            )
        if _ta(lang):
            return (
                "நான் மருத்துவ நோயறிதல் செய்யமாட்டேன் — பொதுவான தகவல் மட்டும். "
                "தீவிரமானால் மருத்துவரை அணுகுங்கள். பராமரிப்பாளர் வேண்டுமானால் சொல்லுங்கள்."
            )
        return (
            "I don’t diagnose — only general information. See a clinician for serious symptoms. "
            "If you want a caregiver, just ask me to find one."
        )

    # general / fallback — keep the floor open; Gemini should usually replace this.
    if _si(lang):
        return "හරි, තේරුණා. තවත් කියන්න — නැත්නම් caregiver කෙනෙක් හොයන්න කියන්න."
    if _ta(lang):
        return "சரி, புரிந்தது. தொடர்ந்து சொல்லுங்கள் — அல்லது பராமரிப்பாளர் தேடச் சொல்லுங்கள்."
    return "Got it. Keep talking — or ask me to find a caregiver when you want one."


def _history_blurb(history: list | None) -> str:
    if not history:
        return ""
    lines: list[str] = []
    for turn in history[-8:]:
        if not isinstance(turn, dict):
            continue
        role = "User" if turn.get("role") == "user" else "Serah"
        text = (turn.get("text") or "").strip().replace("\n", " ")
        if not text:
            continue
        lines.append(f"{role}: {text[:240]}")
    return "\n".join(lines)


def _match_grounding(match: dict | None, lang: str) -> str:
    if not match or not match.get("results"):
        return "No caregiver list is active."
    rows = []
    for row in match["results"][:5]:
        if not isinstance(row, dict):
            continue
        name = row.get("display_name") or f"caregiver {row.get('caregiver_id')}"
        xai = localize_explanation(row.get("explanation") or "", lang)
        rows.append(f"#{row.get('rank')} {name}: {xai}")
    return "Grounded VEHMF results (do not invent names or ranks):\n" + "\n".join(rows)


def gemini_chat_reply(
    text: str,
    lang: str,
    *,
    situation: str,
    has_prior_match: bool,
    match: dict | None = None,
    history: list | None = None,
    user_id: int | None = None,
) -> SerahLine | None:
    """Optional Gemini line; returns None to fall back to stub (or rate_limited stub)."""
    backend = resolve_chat_backend()
    if backend != "gemini":
        return None
    # Hire/request copy stays deterministic (points at client action executor).
    if situation in {"request", "view_profile", "describe_caregiver", "request_status"}:
        return None

    allowed, reason = gemini_chat_allowed(user_id)
    if not allowed:
        if reason == "rate_limited":
            stub = stub_for_situation(situation, lang, text=text, match=match)
            return SerahLine(text=stub, source="rate_limited")
        return None

    top_name = ""
    top_xai = ""
    if match and match.get("results"):
        top = match["results"][0]
        top_name = top.get("display_name") or ""
        top_xai = localize_explanation(top.get("explanation") or "", lang)

    guidance = {
        "thanks": "They said thanks. Acknowledge warmly. Do NOT pitch finding caregivers again.",
        "goodbye": "They are leaving. Say a short goodbye. Do NOT restart caregiver matching.",
        "affirm": "They acknowledged. Brief confirm. Mention matches only if already shown.",
        "greeting": "Greet briefly as Serah. Offer to chat about anything, or find a caregiver if they ask.",
        "smalltalk": "Answer who you are briefly. Continue the conversation. No diagnosis.",
        "faq": "Explain Care Plus in one short spoken beat, then invite them to keep talking.",
        "about_match": f"Explain using ONLY the grounded list. Top={top_name}. XAI={top_xai}.",
        "advice": "General info only; no diagnosis/prescription. Offer caregiver search only if asked.",
        "post_match_chat": (
            "Continue naturally. You may refer to the grounded match list. "
            "Do not re-run or invent rankings. If they want a new search they must ask."
        ),
        "cancel": "Acknowledge canceling the search, then stay open for ordinary chat.",
        "emergency": "Urge real emergency services first; offer caregiver search second.",
        "general": (
            "Continue the conversation as a warm, useful companion. Answer what they said. "
            "If they want a person to care for them, do not pretend matches are visible and "
            "do not say VEHMF is running or that results will appear later — matching is a "
            "separate engine route. Only invite a caregiver search if they have not already asked."
        ),
    }.get(
        situation, "Be warm and brief. Continue the conversation. Don’t force caregiver matching."
    )

    history_block = _history_blurb(history)
    match_block = (
        _match_grounding(match, lang)
        if (match or situation in {"about_match", "post_match_chat"})
        else ""
    )

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        resp = model.generate_content(
            (
                "You are Serah, Care Plus voice assistant for Sri Lanka. "
                "Reply in 1–3 short spoken sentences that continue the dialogue. "
                "Never invent caregiver names, scores, or rankings. "
                "Never pick or re-rank caregivers — VEHMF does that locally when they ask. "
                "Never say you are waiting for VEHMF, that matching is in progress, or that "
                "you will show caregiver results later. If no caregiver list is in the grounding "
                "block, do not mention matching, ranking, cards, or results on screen. "
                "Do not say goodbye unless the user is clearly leaving. "
                f"Situation={situation}. has_prior_match={has_prior_match}. "
                f"Guidance: {guidance}\n"
                f"{match_block}\n"
                f"Recent conversation:\n{history_block or '(none yet)'}\n"
                f"Reply ONLY in {_display_lang(lang)} — never mix English if the user chose Sinhala or Tamil. "
                f"Patient just said: {text}"
            ),
            generation_config={"temperature": 0.45, "max_output_tokens": 180},
        )
        out = (resp.text or "").strip()
        if out:
            return SerahLine(text=out, source="gemini")
        return None
    except Exception:
        logger.exception("Serah situational chat failed")
        return None


def local_chat_reply(
    text: str,
    lang: str,
    *,
    situation: str,
    has_prior_match: bool,
    match: dict | None = None,
    history: list | None = None,
) -> SerahLine | None:
    """Optional on-prem OpenAI-compatible chat (Step 97). Never ranks caregivers."""
    from .local_llm import local_llm_configured, post_chat_completion

    if not local_llm_configured():
        return None
    if situation in {"request", "view_profile", "describe_caregiver", "request_status"}:
        return None

    top_name = ""
    top_xai = ""
    if match and match.get("results"):
        top = match["results"][0]
        top_name = top.get("display_name") or ""
        top_xai = localize_explanation(top.get("explanation") or "", lang)

    guidance = (
        f"Situation={situation}. has_prior_match={has_prior_match}. "
        f"Top caregiver context (do not invent): {top_name} / {top_xai}. "
        "Reply in 1–3 short spoken sentences. Never invent caregiver rankings."
    )
    system = (
        "You are Serah, Care Plus voice assistant for Sri Lanka. "
        "Never pick or re-rank caregivers — VEHMF does that locally. "
        f"Reply ONLY in {_display_lang(lang)}."
    )
    user_content = (
        f"{guidance}\n"
        f"{_match_grounding(match, lang) if match else ''}\n"
        f"Recent conversation:\n{_history_blurb(history) or '(none yet)'}\n"
        f"Patient just said: {text}"
    )
    out = post_chat_completion(system=system, user=user_content)
    if not out:
        return None
    return SerahLine(text=out, source="local_llm")


def serah_reply(
    *,
    text: str,
    lang: str,
    situation: str,
    has_prior_match: bool = False,
    match: dict | None = None,
    history: list | None = None,
    user_id: int | None = None,
) -> SerahLine:
    backend = resolve_chat_backend()
    if backend == "local":
        local = local_chat_reply(
            text,
            lang,
            situation=situation,
            has_prior_match=has_prior_match,
            match=match,
            history=history,
        )
        if local is not None:
            return local
        return SerahLine(
            text=stub_for_situation(situation, lang, text=text, match=match),
            source="stub",
        )

    cloud = gemini_chat_reply(
        text,
        lang,
        situation=situation,
        has_prior_match=has_prior_match,
        match=match,
        history=history,
        user_id=user_id,
    )
    if cloud is not None:
        return cloud
    return SerahLine(
        text=stub_for_situation(situation, lang, text=text, match=match),
        source="stub",
    )
