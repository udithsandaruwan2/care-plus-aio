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
    r"\b(caregiver|care[\s-]*giver|nurses?|carer|attendant|vehmf|"
    r"find\s*(me\s*)?(a\s*)?(caregiver|nurse|carer|attendant|someone|somebody|person)|"
    r"(need|want|get)\s*(me\s*)?(a\s*)?(caregiver|nurse|carer|attendant)|"
    r"(looking|search(ing)?)\s*for\s*(a\s*)?(caregiver|nurse|carer|attendant|someone|somebody|person|care)|"
    r"help\s+me\s+find|"
    r"(start|begin|run)\s+(the\s+)?(search|match|matching|vehmf)|"
    r"(search|match|find)\s+now|"
    r"go\s+ahead\s+(and\s+)?(search|match|find)|"
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
    r"\b(request\s*(the\s*)?(first|top|#?\s*\d+|this|her|him|them)|"
    r"send\s*(the\s*)?(care\s*)?request|"
    r"book\s*(the\s*)?(first|top|#?\s*\d+|them|him|her)|"
    r"hire(\s*(the\s*)?(first|top|#?\s*\d+|them|him|her))?|"
    r"choose\s*(the\s*)?(first|top|#?\s*\d+)|"
    r"i\s*want\s*(the\s*)?(first|top|#?\s*\d+|this\s*one)|"
    r"select\s*(#?\s*)?\d+|"
    r"yes[,.]?\s*(send|request|hire|book)|"
    r"go\s+ahead\s+(and\s+)?(send|request|hire|book))\b|"
    r"ඉල්ලීම|තෝර|முதல்\s*நபர்|முன்பதிவு",
    re.I,
)

_VIEW_PROFILE = re.compile(
    r"\b("
    r"(review|check|open|show|see|look\s*at)\s+"
    r"((his|her|their|the|a)\s+)?(profile|details?)|"
    r"(review|check|open|show)\s+(#?\s*\d+|number\s*\d+|"
    r"the\s*(first|second|third|top)|[\w'-]{2,})|"
    r"go\s+ahead\s+(and\s+)?(check|open|review|show)|"
    r"yes[,.]?\s*(check|open|review|show)\s*(his|her|their|the)?\s*(profile)?"
    r")\b|"
    r"පැතිකඩ|சுயவிவரம்",
    re.I,
)

_DESCRIBE = re.compile(
    r"\b(tell\s*me\s*more|read\s*(me\s*)?(their|his|her|the)?\s*(details?|profile|bio)|"
    r"describe\s*(them|him|her|this|the\s*caregiver)?|"
    r"what\s*(can\s*you\s*tell|do\s*you\s*know)\s*about)\b|"
    r"වැඩිපුර|மேலும்\s*சொல்லு",
    re.I,
)

_REQUEST_STATUS = re.compile(
    r"\b("
    r"any\s*(update|news|response|word)|"
    r"(what'?s|what\s+is)\s*(the\s*)?(status|update)|"
    r"(request|booking)\s*status|"
    r"(did|has)\s*(they|he|she|the\s*caregiver)\s*(accept|respond|reply|answer)|"
    r"still\s*waiting|"
    r"have\s*they\s*(accepted|responded|replied)|"
    r"check\s*(on\s*)?(the\s*)?(request|status)"
    r")\b|"
    r"තත්ත්වය|நிலைமை|நிலை",
    re.I,
)

_SELECT_PACKAGE = re.compile(
    r"\b("
    r"(select|choose|pick|take|want)\s+(the\s+)?(package|plan|option)|"
    r"(package|plan)\s*(#?\s*\d+|number\s*\d+|one|two|three|first|second|third)|"
    r"(#?\s*\d+|number\s*\d+|first|second|third)\s+(package|plan|option)|"
    r"basic(\s+home)?(\s+care)?|"
    r"intermediate(\s+nursing)?|"
    r"advanced(\s+clinical)?(\s+care)?|"
    r"night\s+respite|"
    r"pediatric|"
    r"palliative|"
    r"post[\s-]*surgery|"
    r"standard(\s+(package|plan|care))?|"
    r"\d{1,3}\s*days?|"
    r"(a\s+)?(week|fortnight|month)\s*(of\s+care)?|"
    r"(add|with|include|plus)\s+(meals?|food|meal\s+support|transport|supplies|hospital\s+escort|physio)"
    r")\b|"
    r"පැකේජ|பேக்கேஜ்",
    re.I,
)

_CONFIRM_CHECKOUT = re.compile(
    r"\b("
    r"continue\s+(to\s+)?(payment|pay|checkout)|"
    r"(go\s+to|open)\s+(payment|pay|checkout)|"
    r"(confirm|ready\s+for|proceed\s+(to\s+)?|start)\s*(the\s*)?(checkout|payment|order)|"
    r"checkout(\s+now)?|"
    r"create\s+(the\s+)?order|"
    r"take\s+me\s+to\s+(pay|payment|checkout)"
    r")\b|"
    r"ගෙවීම|செலுத்த",
    re.I,
)

# Last Serah line offered opening a profile / sending a request (yes-after-offer).
_OFFER_PROFILE = re.compile(
    r"(check|open|review|see|look\s*at).{0,40}profile|"
    r"profile.{0,24}(check|open|review)|"
    r"would\s+you\s+like.{0,40}(profile|review|details)",
    re.I,
)

_OFFER_REQUEST = re.compile(
    r"(send|make).{0,24}(care\s*)?request|"
    r"(request|hire|book).{0,24}(them|him|her|caregiver)|"
    r"go\s+ahead.{0,24}(request|hire|book)|"
    r"shall\s+i\s+(send|request|hire)",
    re.I,
)

_OFFER_PACKAGE = re.compile(
    r"(pick|choose|select).{0,24}package|"
    r"here are a few packages|"
    r"package options|"
    r"say .{0,40}(basic|days|package)",
    re.I,
)

_OFFER_CHECKOUT = re.compile(
    r"continue to payment|"
    r"tap\s+pay|"
    r"ready to checkout|"
    r"confirm.{0,20}package|"
    r"when you'?re ready",
    re.I,
)

_CANCEL = re.compile(
    r"\b(never\s*mind|cancel|forget\s*it|stop\s*(searching|matching)|"
    r"don'?t\s*(need|want)\s*(a\s*)?caregiver)\b|"
    r"එපා|නවත්ත|வேண்டாம்|நிறுத்து",
    re.I,
)


# Short “go” phrases after chips are filled (ASR often just says "start").
_LAUNCH = re.compile(
    r"^(start|begin|go|search|find|match|go\s+ahead)"
    r"(\s+(it|now|please|searching|matching))?[\s!.]*$|"
    r"^(පටන්|ආරම්භ|හොයන්න)([\s!.]*|\s+ගන්න[\s!.]*)$|"
    r"^(தொடங்கு|தேடு)[\s!.]*$",
    re.I,
)


def _complete(intent: dict) -> bool:
    """VEHMF can rank once a condition is known, or language + care level are set."""
    if (intent.get("condition") or "").strip():
        return True
    return bool((intent.get("language") or "").strip() and (intent.get("care_level") or "").strip())


def is_care_seek(text: str) -> bool:
    raw = (text or "").strip()
    return bool(_MATCH_SEEK.search(raw) or _LAUNCH.match(raw))


def needs_slot_extraction(text: str, *, has_prior_match: bool = False) -> bool:
    """True when this turn may run VEHMF — worth a (slower) intent extract."""
    raw = (text or "").strip()
    if not raw:
        return False
    if _EMERGENCY.search(raw) or _MATCH_SEEK.search(raw) or _LAUNCH.match(raw) or _NEW_SEARCH.search(raw):
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
    last_serah_text: str = "",
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
        # Bare "yes" after Serah offered a profile, care request, package, or checkout.
        if last_serah_text:
            low = last_serah_text.lower()
            # After pay screen open ("tap Pay"), yes must not auto-charge.
            if "tap pay" in low or "won’t charge" in low or "wont charge" in low:
                return RouteDecision("CHAT", "affirm")
            if "continue to payment" in low or (
                _OFFER_CHECKOUT.search(last_serah_text) and "package" in low
            ):
                return RouteDecision("ACTION", "confirm_checkout")
            if _OFFER_PACKAGE.search(last_serah_text):
                return RouteDecision("ACTION", "select_package")
            if has_prior_match:
                if _OFFER_PROFILE.search(last_serah_text):
                    return RouteDecision("ACTION", "view_profile")
                if _OFFER_REQUEST.search(last_serah_text):
                    return RouteDecision("ACTION", "request")
        return RouteDecision("CHAT", "affirm")

    # 3) Greetings / identity / FAQ (unless also seeking care)
    if _GREETING.search(raw) and not _MATCH_SEEK.search(raw):
        return RouteDecision("CHAT", "greeting")
    if _SMALLTALK.search(raw) and not _MATCH_SEEK.search(raw):
        return RouteDecision("CHAT", "smalltalk")
    if _FAQ.search(raw) and not _MATCH_SEEK.search(raw):
        return RouteDecision("CHAT", "faq")

    # Status check can run with or without visible cards (poll uses careRequestId).
    if _REQUEST_STATUS.search(raw):
        return RouteDecision("ACTION", "request_status")

    # Checkout / package selection (accepted-request funnel; needs match context).
    if _CONFIRM_CHECKOUT.search(raw):
        return RouteDecision("ACTION", "confirm_checkout")
    if (has_prior_match or has_history_match) and _SELECT_PACKAGE.search(raw):
        return RouteDecision("ACTION", "select_package")

    # 4) Questions about a prior match (session memory — cards may be off-screen)
    if has_history_match and _ABOUT_MATCH.search(raw):
        return RouteDecision("CHAT", "about_match")

    # 5) Post-match conversation while caregiver cards are visible on screen
    if has_prior_match:
        if _VIEW_PROFILE.search(raw):
            return RouteDecision("ACTION", "view_profile")
        if _DESCRIBE.search(raw):
            return RouteDecision("ACTION", "describe_caregiver")
        if _ACTION.search(raw):
            return RouteDecision("ACTION", "request")
        if _REFINE.search(raw):
            return RouteDecision("REFINE", "refine")
        if _NEW_SEARCH.search(raw):
            return RouteDecision("MATCH", "new_search", clear_match=True)
        if _MATCH_SEEK.search(raw) or _LAUNCH.match(raw):
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

    if _MATCH_SEEK.search(raw) or _LAUNCH.match(raw):
        if _complete(intent):
            return RouteDecision("MATCH", "match")
        return RouteDecision("CLARIFY", "clarify")

    if _ADVICE.search(raw):
        return RouteDecision("CHAT", "advice")

    # General talk stays in CHAT. Slot-filling CLARIFY only after an explicit seek.
    return RouteDecision("CHAT", "general")
