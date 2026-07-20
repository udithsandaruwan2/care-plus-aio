"""Situation-aware Serah replies (stub + optional rate-limited Gemini chat)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings

from .policy import gemini_chat_allowed, resolve_chat_backend

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SerahLine:
    text: str
    """stub | gemini | rate_limited — never used for caregiver ranking."""
    source: str


def _si(lang: str) -> bool:
    return lang.startswith("si")


def _ta(lang: str) -> bool:
    return lang.startswith("ta")


def stub_for_situation(
    situation: str,
    lang: str,
    *,
    text: str = "",
    match: dict | None = None,
) -> str:
    """Deterministic spoken replies for each conversation situation."""
    top = None
    if match and match.get("results"):
        top = match["results"][0]
    name = (top or {}).get("display_name") or ""

    if situation == "thanks":
        if _si(lang):
            return "සාදරයෙන්! තවත් උදව් අවශ්‍ය නම් කතා කරන්න. සුවයක් වේවා."
        if _ta(lang):
            return "மகிழ்ச்சி! மேலும் உதவி வேண்டுமானால் சொல்லுங்கள். நலமாக இருங்கள்."
        return "You’re welcome! I’m here if you need anything else. Take care."

    if situation == "goodbye":
        if _si(lang):
            return "බලමු! Care Plus එකේ ඕනෑම වෙලාවක ආයෙත් කතා කරන්න."
        if _ta(lang):
            return "சந்திப்போம்! தேவைப்பட்டால் மீண்டும் Care Plus-இல் பேசுங்கள்."
        return "Goodbye — come back anytime you need Care Plus."

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
            return "வணக்கம், நான் Serah. பேசுங்கள் — பராமரிப்பு கேள்வி அல்லது பராமரிப்பாளர் தேவை என்றால் சொல்லுங்கள்."
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
        explanation = (top or {}).get("explanation") or ""
        if _si(lang):
            return (
                f"{name or 'ඉහළම match'} ගැන: {explanation or 'medical/skill match හොඳයි'}. "
                "වෙනත් කෙනෙක් ඕනේ නම් කියන්න — උදා: closer, Tamil only."
            )
        if _ta(lang):
            return (
                f"{name or 'சிறந்த match'} பற்றி: {explanation or 'திறன் பொருத்தம் நன்று'}. "
                "வேறு நபர் வேண்டுமானால் சொல்லுங்கள் — எ.கா. closer, Tamil only."
            )
        return (
            f"About {name or 'the top match'}: {explanation or 'strong skill match'}. "
            "Want someone else? Say closer, another, or Tamil only."
        )

    if situation == "request":
        if _si(lang):
            return (
                f"{name or 'මේ caregiver'} request කරන්න hire flow එක (Step 23) ඉක්මනින් එයි. "
                "දැන් Browse එකෙන් profile බලන්න."
            )
        if _ta(lang):
            return (
                f"{name or 'இந்த பராமரிப்பாளர்'} கோரிக்கை hire flow (Step 23) விரைவில் வரும். "
                "இப்போது Browse-இல் profile பாருங்கள்."
            )
        return (
            f"Requesting {name or 'this caregiver'} will use the hire flow (Step 23). "
            "For now, open their profile from Browse."
        )

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

    # general / fallback
    if _si(lang):
        return "අහන්න පුළුවන් — care ප්‍රශ්නයක්, හෝ caregiver කෙනෙක් සොයමුද කියලා."
    if _ta(lang):
        return "கேளுங்கள் — பராமரிப்பு கேள்வி, அல்லது பராமரிப்பாளரைத் தேடலாமா என்று."
    return "I’m listening — ask a care question, or ask me to find a caregiver."


def gemini_chat_reply(
    text: str,
    lang: str,
    *,
    situation: str,
    has_prior_match: bool,
    match: dict | None = None,
    user_id: int | None = None,
) -> SerahLine | None:
    """Optional Gemini line; returns None to fall back to stub (or rate_limited stub)."""
    backend = resolve_chat_backend()
    if backend != "gemini":
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
        top_xai = top.get("explanation") or ""

    guidance = {
        "thanks": "They said thanks. Acknowledge warmly. Do NOT pitch finding caregivers again.",
        "goodbye": "They are leaving. Say a short goodbye. Do NOT restart caregiver matching.",
        "affirm": "They acknowledged. Brief confirm. Mention matches only if already shown.",
        "greeting": "Greet briefly. Offer chat OR caregiver search — don’t force matching.",
        "smalltalk": "Answer who you are briefly. No diagnosis.",
        "faq": "Explain Care Plus in one short spoken beat.",
        "about_match": f"Explain the top match using this XAI only: {top_xai}. Name={top_name}.",
        "advice": "General info only; no diagnosis/prescription. Offer caregiver search only if asked.",
        "post_match_chat": "Matches already on screen. Respond naturally; don’t re-list caregivers unless asked.",
        "cancel": "Acknowledge canceling the search.",
        "emergency": "Urge real emergency services first; offer caregiver search second.",
        "general": "Be a warm short companion. Only invite caregiver search if they ask.",
    }.get(situation, "Be warm and brief. Don’t force caregiver matching.")

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        resp = model.generate_content(
            (
                "You are Serah, Care Plus voice assistant for Sri Lanka. "
                "Reply in 1–2 short spoken sentences. Never invent caregiver names or rankings. "
                "Never pick or re-rank caregivers — VEHMF does that locally. "
                f"Situation={situation}. has_prior_match={has_prior_match}. "
                f"Guidance: {guidance} "
                f"Prefer reply language matching BCP-47 {lang}. "
                f"Patient said: {text}"
            ),
            generation_config={"temperature": 0.35},
        )
        out = (resp.text or "").strip()
        if out:
            return SerahLine(text=out, source="gemini")
        return None
    except Exception:
        logger.exception("Serah situational chat failed")
        return None


def serah_reply(
    *,
    text: str,
    lang: str,
    situation: str,
    has_prior_match: bool = False,
    match: dict | None = None,
    user_id: int | None = None,
) -> SerahLine:
    cloud = gemini_chat_reply(
        text,
        lang,
        situation=situation,
        has_prior_match=has_prior_match,
        match=match,
        user_id=user_id,
    )
    if cloud is not None:
        return cloud
    return SerahLine(
        text=stub_for_situation(situation, lang, text=text, match=match),
        source="stub",
    )
