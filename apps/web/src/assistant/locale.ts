import type { UiVoiceLanguage } from './uiVoiceLanguage';

const XAI_EN_TO_LOCAL: Record<string, { si: string; ta: string }> = {
  'strong medical/skill match': {
    si: 'වෛද්‍ය හා කුසලතා ගැලපීම ඉතා හොඳයි',
    ta: 'மருத்துவ/திறன் பொருத்தம் வலுவானது',
  },
  'highly rated by similar patients': {
    si: 'සමාන රෝගීන්ගෙන් ඉහළ ශ්‍රේණිගත කිරීමක් ලැබී ඇත',
    ta: 'ஒத்த நோயாளிகளால் உயர் மதிப்பீடு',
  },
  'very close / short travel time': {
    si: 'ඔබට ඉතා ආසන්න / ගමන් කාලය අඩුයි',
    ta: 'மிக அருகில் / குறுகிய பயண நேரம்',
  },
  'high trust & completion record': {
    si: 'විශ්වාසය සහ සේවා සම්පූර්ණතාව ඉහළයි',
    ta: 'நம்பிக்கை மற்றும் பூர்த்தி பதிவு உயர்ந்தது',
  },
};

export function localizeExplanation(explanation: string, lang: UiVoiceLanguage): string {
  if (lang === 'English' || !explanation) return explanation;
  const key = lang === 'Sinhala' ? 'si' : 'ta';
  const prefix = 'Matched because: ';
  if (explanation.startsWith(prefix)) {
    const reason = explanation.slice(prefix.length).replace(/\.$/, '').trim();
    const hit = XAI_EN_TO_LOCAL[reason];
    if (hit) {
      if (key === 'si') return `ගැලපෙන්නේ මෙම නිසාවෙන්: ${hit.si}.`;
      return `பொருந்துவதற்கான காரணம்: ${hit.ta}.`;
    }
  }
  for (const [en, loc] of Object.entries(XAI_EN_TO_LOCAL)) {
    if (explanation.includes(en)) {
      if (key === 'si') return `ගැලපෙන්නේ මෙම නිසාවෙන්: ${loc.si}.`;
      return `பொருந்துவதற்கான காரணம்: ${loc.ta}.`;
    }
  }
  return explanation;
}

const CHIP_LABELS: Record<
  UiVoiceLanguage,
  { condition: string; language: string; care_level: string; urgency: string; empty: string }
> = {
  Sinhala: {
    condition: 'රෝගය',
    language: 'භාෂාව',
    care_level: 'සේවා මට්ටම',
    urgency: 'අවශ්‍යතාව',
    empty: 'තවම විස්තර නැහැ — තත්ත්වය, භාෂාව සහ සේවා මට්ටම කියන්න.',
  },
  Tamil: {
    condition: 'நிலை',
    language: 'மொழி',
    care_level: 'பராமரிப்பு நிலை',
    urgency: 'அவசரம்',
    empty: 'விவரங்கள் இல்லை — நிலை, மொழி, பராமரிப்பு அளவைச் சொல்லுங்கள்.',
  },
  English: {
    condition: 'Condition',
    language: 'Language',
    care_level: 'Care level',
    urgency: 'Urgency',
    empty: 'No care details yet — tell Serah the condition, language, and support level.',
  },
};

export function chipLabels(lang: UiVoiceLanguage) {
  return CHIP_LABELS[lang];
}

const CARE_LEVEL_LABELS: Record<UiVoiceLanguage, Record<string, string>> = {
  Sinhala: { basic: 'මූලික', intermediate: 'මධ්‍යම', advanced: 'උසස්' },
  Tamil: { basic: 'அடிப்படை', intermediate: 'இடைநிலை', advanced: 'மேம்பட்ட' },
  English: { basic: 'basic', intermediate: 'intermediate', advanced: 'advanced' },
};

export function localizeCareLevel(
  level: string | undefined,
  lang: UiVoiceLanguage,
): string | undefined {
  if (!level) return level;
  return CARE_LEVEL_LABELS[lang][level] ?? level;
}

const MATCH_UI: Record<
  UiVoiceLanguage,
  { title: string; score: string; viewProfile: string; request: string; noMatches: string }
> = {
  Sinhala: {
    title: 'හොඳම ගැලපීම්',
    score: 'ලකුණු',
    viewProfile: 'පැතිකඩ බලන්න',
    request: 'මෙම පරිචාරක ඉල්ලන්න',
    noMatches: 'තවම පරිචාරකයින් හමු නොවීය. තත්ත්වය හෝ භාෂාව එකතු කරන්න.',
  },
  Tamil: {
    title: 'சிறந்த பொருத்தங்கள்',
    score: 'மதிப்பு',
    viewProfile: 'சுயவிவரம்',
    request: 'இந்த பராமரிப்பாளரைக் கோருங்கள்',
    noMatches: 'பொருத்தம் இல்லை. நிலை அல்லது மொழியைச் சேர்த்து முயலவும்.',
  },
  English: {
    title: 'Best matches',
    score: 'score',
    viewProfile: 'View profile',
    request: 'Request this caregiver',
    noMatches: 'No caregivers matched yet. Add a condition or language, or try nearby cities.',
  },
};

export function matchUi(lang: UiVoiceLanguage) {
  return MATCH_UI[lang];
}

const MATCH_SEARCH: Record<
  UiVoiceLanguage,
  { searching: string; ready: string; keepChatting: string; noMatches: string; thinking: string[] }
> = {
  Sinhala: {
    searching: 'VEHMF පරිචාරකයින් සොයමින්…',
    ready: 'ගැලපීම් සූදානම්',
    keepChatting: 'සොයන අතර කතා කරගෙන යන්න පුළුවන්.',
    noMatches: 'තවම පරිචාරකයින් හමු නොවීය.',
    thinking: [
      'ආසන්න පරිචාරකයින් පරීක්ෂා කරමින්…',
      'කුසලතා සහ භාෂාව අනුව ශ්‍රේණිගත කරමින්…',
      'විශ්වාසය සහ දුර ලකුණු කරමින්…',
      'VEHMF ලැයිස්තුව බර කරමින්…',
    ],
  },
  Tamil: {
    searching: 'VEHMF பராமரிப்பாளர்களைத் தேடுகிறது…',
    ready: 'பொருத்தங்கள் தயார்',
    keepChatting: 'தேடும்போது பேசிக்கொண்டே இருக்கலாம்.',
    noMatches: 'பொருத்தம் இல்லை.',
    thinking: [
      'அருகிலுள்ள பராமரிப்பாளர்களைச் சரிபார்க்கிறது…',
      'திறன் மற்றும் மொழி அடிப்படையில் தரவரிசை…',
      'நம்பிக்கை மற்றும் தூரத்தை மதிப்பிடுகிறது…',
      'VEHMF பட்டியலை எடைபோடுகிறது…',
    ],
  },
  English: {
    searching: 'VEHMF is ranking caregivers…',
    ready: 'Matches ready',
    keepChatting: 'We can keep chatting while this runs.',
    noMatches: 'No caregivers matched yet.',
    thinking: [
      'Checking who is nearby…',
      'Ranking by skill and language…',
      'Scoring trust and distance…',
      'VEHMF is weighting this list…',
    ],
  },
};

export function matchSearchCopy(lang: UiVoiceLanguage) {
  return MATCH_SEARCH[lang];
}

const MATCH_VOICE: Record<UiVoiceLanguage, { finding: string; resultsReady: string }> = {
  Sinhala: {
    finding:
      'මම එකක් සොයනවා. සොයන අතර අපිට කතා කරගෙන යන්න පුළුවන්.',
    resultsReady: 'දැන් ප්‍රතිඵල පෙනෙනවා. කාඩ් බලලා කෙනෙක් තෝරන්න.',
  },
  Tamil: {
    finding:
      'நான் ஒருவரைத் தேடுகிறேன். தேடும்போது பேசிக்கொண்டே இருக்கலாம்.',
    resultsReady: 'இப்போது முடிவுகளைப் பார்க்கலாம். அட்டைகளைப் பார்த்து ஒருவரைத் தேர்ந்தெடுங்கள்.',
  },
  English: {
    finding: "I'm finding one for you. We can keep chatting while I search.",
    resultsReady: 'Now you can see the results. Look at the cards and pick someone.',
  },
};

export function matchVoiceCopy(lang: UiVoiceLanguage) {
  return MATCH_VOICE[lang];
}

const STATE_COPY_LOCAL: Record<UiVoiceLanguage, Record<string, string>> = {
  Sinhala: {
    IDLE: 'කතා කරන්න ටැප් කරන්න',
    LISTENING: 'ඇසෙනවා…',
    THINKING: 'පිළිතුරු දෙනවා…',
    CLARIFYING: 'තව ටිකක් විස්තර…',
    SPEAKING: 'මෙහෙම ඇසුණා',
    CHAT_REPLY: 'Serah පිළිතුරු දෙනවා…',
    MATCHING: 'හොඳම ගැලපීම සොයමින්…',
    RESULTS: 'ගැලපීම් සූදානම්',
    EMERGENCY: 'හදිසි අවධානය',
  },
  Tamil: {
    IDLE: 'பேச தட்டுங்கள்',
    LISTENING: 'கேட்கிறது…',
    THINKING: 'பதிலளிக்கிறது…',
    CLARIFYING: 'இன்னும் சிறிது விவரம்…',
    SPEAKING: 'இதைக் கேட்டேன்',
    CHAT_REPLY: 'Serah பதிலளிக்கிறார்…',
    MATCHING: 'சிறந்த பொருத்தம் தேடுகிறது…',
    RESULTS: 'பொருத்தங்கள் தயார்',
    EMERGENCY: 'அவசர எச்சரிக்கை',
  },
  English: {
    IDLE: 'Tap to speak',
    LISTENING: 'Listening…',
    THINKING: 'Replying…',
    CLARIFYING: 'One more detail…',
    SPEAKING: "Here's what I heard",
    CHAT_REPLY: 'Serah is replying…',
    MATCHING: 'Finding your best match…',
    RESULTS: 'Matches ready',
    EMERGENCY: 'Health alert',
  },
};

export function stateCopy(state: string, lang: UiVoiceLanguage): string {
  return STATE_COPY_LOCAL[lang][state] ?? STATE_COPY_LOCAL.English[state] ?? state;
}
