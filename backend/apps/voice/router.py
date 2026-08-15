"""Turn router — classify natural conversation into Care Plus routes.

Situations (fine-grained) map to API routes:
  CHAT | MATCH | CLARIFY | REFINE | ACTION | EMERGENCY

Critical rule: after a successful match, do **not** re-run VEHMF just because
goal chips are still filled. Only MATCH/REFINE on explicit care-seeking /
refine language.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    route: str  # CHAT | MATCH | CLARIFY | REFINE | ACTION | EMERGENCY
    situation: str
    clear_match: bool = False  # UI may drop cards (new search / goodbye)


# ── Phrase banks (English + Sinhala + Tamil common forms) ─────────────────

_EMERGENCY = re.compile(
    r"\b(emergency|urgent|asap|immediately|critical|ambulance|911|119)\b|"
    r"හදිසි|අනතුර|ඉක්මනින්|දැන්ම|அவசரம்|உடனடி",
    re.I,
)

_THANKS = re.compile(
    r"\b(thanks|thank\s*you|thx|ty|appreciate|grateful)\b|"
    r"ස්තූත|ස්තුත|istuti|bohoma\s*stuti|நன்றி|nanri",
    re.I,
)

_GOODBYE = re.compile(
    r"\b(bye|goodbye|good\s*bye|see\s*you|that'?s\s*all|"
    r"i'?m\s*done|nothing\s*else|no\s*more)\b|"
    r"\btake\s*care(?!\s+of)\b|"
    r"ගිහින්|බලමු|හමුවෙමු|போய்ட்டு|போறேன்|சந்திப்போம்",
    re.I,
)

_GREETING = re.compile(
    r"^(hi|hello|hey|good\s*(morning|afternoon|evening)|yo)\b|"
    r"ආයුබෝවන්|ආයුබෝ|හායි|ayubowan|வணக்கம்|vanakkam",
    re.I,
)

_AFFIRM = re.compile(
    r"^(ok|okay|alright|all\s*right|fine|great|perfect|cool|nice|yes|yeah|yep|"
    r"sure|got\s*it|understood|sounds\s*good|awesome)[\s!.]*$|"
    r"^(හරි|හොඳයි|ඔව්|ඔව්වා|සුපිරි|சரி|நன்றி|ஆம்|சரிங்க)[\s!.]*$",
    re.I,
)

_SMALLTALK = re.compile(
    r"\b(how\s*are\s*you|who\s*are\s*you|what'?s\s*your\s*name|your\s*name|"
    r"are\s*you\s*(an\s*)?ai|what\s*can\s*you\s*do|help\s*me)\b|"
    r"කොහොමද|ඔයා\s*කවුද|නම\s*මොකක්ද|எப்படி\s*இருக்க|யார்\s*நீ|உன்\s*பெயர்",
    re.I,
)

_FAQ = re.compile(
    r"\b(how\s*does\s*(this|care\s*plus|it)\s*work|what\s*is\s*care\s*plus|"
    r"how\s*do\s*i\s*(find|book|request)|explain\s*(the\s*)?(app|service))\b|"
    r"කොහොමද\s*වැඩ|මේක\s*මොකක්ද|எப்படி\s*வேலை",
    re.I,
)

_ADVICE = re.compile(
    r"\b(tip|advice|suggest|recommend|should\s*i|what\s*(do|can)\s*i\s*do|"
    r"tell\s*me\s*about|information\s*about|symptom)\b|"
    r"උපදෙස්|කියන්න\s*කොහොමද|ஆலோசனை|சொல்லுங்கள்",
    re.I,
)

_ABOUT_MATCH = re.compile(
    r"\b(why\s*(is\s*)?(#?\s*1|number\s*one|the\s*first|top)|"
    r"explain\s*(the\s*)?(match|score|rank|result)|"
    r"tell\s*me\s*about\s*(the\s*)?(first|top|#?\s*1|her|him|them)|"
    r"who\s*is\s*(#?\s*1|first|top)|more\s*(about|detail)s?\s*(on|about)?\s*(#?\s*\d)?)\b|"
    r"ඇයි\s*(එක|පළවෙනි)|විස්තර|ஏன்\s*முதல்|விவரம்",
    re.I,
)

_REFINE = re.compile(
    r"\b(closer|nearer|nearby|another|different|else|other|"
    r"only\s*(tamil|sinhala|english)|"
    r"(tamil|sinhala|english)\s*(only|speakers?)|"
    r"female|male|woman|man|"
    r"within\s*\d+|under\s*\d+|less\s*than\s*\d+\s*km|"
    r"\d+\s*km|"
    r"cheaper|more\s*experienced|advanced|basic\s*only)\b|"
    r"කිට්ටු|ලංකට|වෙනත්|අනෙක්|வேறு|மற்றொரு|அருகில்|பெண்|ஆண்",
    re.I,
)

# Care-seeking: named roles, or "someone to take care of me" (ASR often drops "caregiver").
_MATCH_SEEK = re.compile(
    r"\b(caregiver|care[\s-]*giver|nurses?|carer|attendant|"
    r"find\s*(me\s*)?(a\s*)?(caregiver|nurse|carer|attendant|someone)|"
    r"(need|want|get)\s*(me\s*)?(a\s*)?(caregiver|nurse|carer|attendant)|"
    r"(looking|search(ing)?)\s*for\s*(a\s*)?(caregiver|nurse|carer|attendant|someone)|"
    r"match\s*me|show\s*(me\s*)?(the\s*)?(caregivers?|nurses?|matches|options)|"
    r"book\s*(a\s*)?(caregiver|nurse)|hire\s*(a\s*)?(caregiver|nurse)|"
    r"need\s+(a\s+)?(someone|somebody|person)|"
    r"(someone|somebody|person)\s+(to|who)\s+(take\s*care|look\s*after|care\s+for|help)|"
    r"who\s+can\s+(take\s*care|look\s*after|care\s+for|help)|"
    r"take\s*care\s+of\s+(me|my|him|her|them|us)|"
    r"look\s*after\s+(me|my|him|her|them|us)|"
    r"care\s+for\s+(me|my)\b)\b|"
    r"පරිචාරක|කේර්\s*ගිවර්|රැකබලා|බලාගන්න|"
    r"(හොය|සොය).{0,24}(කෙනෙක්|කෙනෙකු|පරිචාරක|nurse|caregiver)|"
    r"(කෙනෙක්|කෙනෙකු).{0,24}(හොය|සොය)|"
    r"(caregiver|nurse|පරිචාරක).{0,16}(ඕන[ේෙ]?|ඕන)|"
    r"(ඕන[ේෙ]?|ඕන).{0,16}(caregiver|nurse|පරිචාරක)|"
    r"பராமரிப்பாளர்|"
    r"(தேடு|தேவை|வேண்டும்).{0,20}(பராமரிப்பாளர்|nurse|caregiver)|"
    r"(பராமரிப்பாளர்|nurse|caregiver).{0,16}(தேடு|தேவை|வேண்டும்)",
    re.I,
)

_NEW_SEARCH = re.compile(
    r"\b(new\s*(search|request|match)|start\s*over|start\s*again|reset|"
    r"different\s*(condition|problem|disease)|change\s*(the\s*)?(condition|search))\b|"
    r"අලුත්|නැවත\s*පටන්|புதிய\s*தேடல்|மீண்டும்\s*தொடங்கு",
    re.I,
)

_ACTION = re.compile(
    r"\b(request\s*(the\s*)?(first|top|#?\s*1|this|her|him)|"
    r"book\s*(the\s*)?(first|top|#?\s*1|them)|"
    r"hire|choose\s*(the\s*)?(first|top|#?\s*1)|"
    r"i\s*want\s*(the\s*)?(first|top|#?\s*1|this\s*one)|"
    r"select\s*(#?\s*)?\d+)\b|"
    r"ඉල්ලීම|තෝර|முதல்\s*நபர்|முன்பதிவு",
    re.I,
)

_CANCEL = re.compile(
    r"\b(never\s*mind|cancel|forget\s*it|stop\s*(searching|matching)|"
    r"don'?t\s*(need|want)\s*(a\s*)?caregiver)\b|"
    r"එපා|නවත්ත|வேண்டாம்|நிறுத்து",
    re.I,
)


def _complete(intent: dict) -> bool:
    """Engine can run once the care condition is known; language/level default."""
    return bool((intent.get("condition") or "").strip())


def is_care_seek(text: str) -> bool:
    return bool(_MATCH_SEEK.search((text or "").strip()))


def needs_slot_extraction(text: str, *, has_prior_match: bool = False) -> bool:
    """True when this turn may run VEHMF — worth a (slower) intent extract."""
    raw = (text or "").strip()
    if not raw:
        return False
    if _EMERGENCY.search(raw) or _MATCH_SEEK.search(raw) or _NEW_SEARCH.search(raw):
        return True
    if has_prior_match and _REFINE.search(raw):
        return True
    return False


def classify_turn(
    text: str,
    intent: dict,
    *,
    has_prior_match: bool = False,
    has_history_match: bool = False,
) -> RouteDecision:
    """Return route + situation for this utterance."""
    raw = (text or "").strip()
    if not raw:
        return RouteDecision("CHAT", "empty")

    # 1) Safety first
    if _EMERGENCY.search(raw):
        return RouteDecision("EMERGENCY", "emergency")

    # 2) Social closings / acknowledgements (esp. after match)
    if _THANKS.search(raw) and not _MATCH_SEEK.search(raw):
        return RouteDecision("CHAT", "thanks")
    if _GOODBYE.search(raw) and not _MATCH_SEEK.search(raw):
        return RouteDecision("CHAT", "goodbye", clear_match=True)
    if _CANCEL.search(raw):
        return RouteDecision("CHAT", "cancel", clear_match=True)
    if _AFFIRM.match(raw.strip()) and not _MATCH_SEEK.search(raw):
        return RouteDecision("CHAT", "affirm")

    # 3) Greetings / identity / FAQ (unless also seeking care)
    if _GREETING.search(raw) and not _MATCH_SEEK.search(raw):
        return RouteDecision("CHAT", "greeting")
    if _SMALLTALK.search(raw) and not _MATCH_SEEK.search(raw):
        return RouteDecision("CHAT", "smalltalk")
    if _FAQ.search(raw) and not _MATCH_SEEK.search(raw):
        return RouteDecision("CHAT", "faq")

    # 4) Questions about a prior match (session memory — cards may be off-screen)
    if has_history_match and _ABOUT_MATCH.search(raw):
        return RouteDecision("CHAT", "about_match")

    # 5) Post-match conversation while caregiver cards are visible on screen
    if has_prior_match:
        if _ACTION.search(raw):
            return RouteDecision("ACTION", "request")
        if _REFINE.search(raw):
            return RouteDecision("REFINE", "refine")
        if _NEW_SEARCH.search(raw):
            return RouteDecision("MATCH", "new_search", clear_match=True)
        if _MATCH_SEEK.search(raw):
            # New caregiver ask while cards visible — re-match with current/new chips
            if _complete(intent):
                return RouteDecision("MATCH", "rematch")
            return RouteDecision("CLARIFY", "clarify_after_match")
        if _ADVICE.search(raw):
            return RouteDecision("CHAT", "advice")
        # Default after match: stay in conversation, do NOT re-run VEHMF
        return RouteDecision("CHAT", "post_match_chat")

    # 6) Pre-match / open dialogue
    if _NEW_SEARCH.search(raw):
        if _complete(intent):
            return RouteDecision("MATCH", "new_search")
        return RouteDecision("CLARIFY", "clarify")

    if _MATCH_SEEK.search(raw):
        if _complete(intent):
            return RouteDecision("MATCH", "match")
        return RouteDecision("CLARIFY", "clarify")

    if _ADVICE.search(raw):
        return RouteDecision("CHAT", "advice")

    # General talk stays in CHAT. Slot-filling CLARIFY only after an explicit seek.
    return RouteDecision("CHAT", "general")
