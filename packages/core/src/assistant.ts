/** Assistant FSM states — Neural Core (docs/FRONTEND.md §4). */
export const AssistantState = {
  IDLE: 'IDLE',
  LISTENING: 'LISTENING',
  THINKING: 'THINKING',
  CLARIFYING: 'CLARIFYING',
  SPEAKING: 'SPEAKING',
  /** Serah is replying in chat (TTS / bubble) without rematching. */
  CHAT_REPLY: 'CHAT_REPLY',
  MATCHING: 'MATCHING',
  RESULTS: 'RESULTS',
  EMERGENCY: 'EMERGENCY',
} as const;

export type AssistantState = (typeof AssistantState)[keyof typeof AssistantState];

/** Intent fields that fill the Goal Ring. */
export const GOAL_FIELDS = ['condition', 'language', 'care_level'] as const;
export type GoalField = (typeof GOAL_FIELDS)[number];

export type IntentDraft = {
  condition?: string;
  language?: 'Sinhala' | 'Tamil' | 'English';
  /** All languages detected (code-switching). */
  languages?: Array<'Sinhala' | 'Tamil' | 'English'>;
  care_level?: 'basic' | 'intermediate' | 'advanced';
  urgency?: 'routine' | 'urgent' | 'critical';
  raw_text?: string;
};

/** How many required Goal Ring segments are filled (0–1). */
export function goalRingProgress(intent: IntentDraft): number {
  const filled = GOAL_FIELDS.filter((f) => Boolean(intent[f])).length;
  return filled / GOAL_FIELDS.length;
}

/** First required field still missing (drives CLARIFYING prompts). */
export function nextMissingField(intent: IntentDraft): GoalField | null {
  return GOAL_FIELDS.find((f) => !intent[f]) ?? null;
}

/** Short status copy per state (English default; UI can localize later). */
export const STATE_COPY: Record<AssistantState, string> = {
  IDLE: 'Tap to speak',
  LISTENING: 'Listening…',
  THINKING: 'Replying…',
  CLARIFYING: 'One more detail…',
  SPEAKING: 'Here’s what I heard',
  CHAT_REPLY: 'Serah is replying…',
  MATCHING: 'Finding your best match…',
  RESULTS: 'Matches ready',
  EMERGENCY: 'Health alert',
};

/** Allowed FSM transitions (docs/FRONTEND.md §4). */
export const TRANSITIONS: Record<AssistantState, AssistantState[]> = {
  IDLE: ['LISTENING', 'EMERGENCY'],
  LISTENING: ['LISTENING', 'THINKING', 'MATCHING', 'EMERGENCY', 'IDLE'],
  THINKING: ['SPEAKING', 'CLARIFYING', 'CHAT_REPLY', 'MATCHING', 'RESULTS', 'EMERGENCY'],
  CLARIFYING: ['LISTENING', 'CHAT_REPLY', 'EMERGENCY'],
  SPEAKING: ['MATCHING', 'CHAT_REPLY', 'IDLE'],
  CHAT_REPLY: ['LISTENING', 'MATCHING', 'RESULTS', 'CLARIFYING', 'IDLE', 'EMERGENCY'],
  MATCHING: ['RESULTS', 'CHAT_REPLY', 'EMERGENCY', 'LISTENING', 'IDLE'],
  RESULTS: ['LISTENING', 'CHAT_REPLY', 'MATCHING', 'CLARIFYING', 'IDLE', 'EMERGENCY'],
  EMERGENCY: ['RESULTS', 'IDLE', 'CHAT_REPLY'],
};

export function canTransition(from: AssistantState, to: AssistantState): boolean {
  return TRANSITIONS[from].includes(to);
}

/** Client hint: this utterance is asking to run VEHMF (not general chat). */
export function looksLikeSearchLaunch(text: string): boolean {
  const raw = (text || '').trim();
  if (!raw) return false;
  return (
    /^(start|begin|go|search|find|match)([\s!.]*|\s+(it|now|please|searching|matching))?$/i.test(
      raw,
    ) ||
    /^go\s+ahead[\s!.]*$/i.test(raw) ||
    /^(පටන්|ආරම්භ|හොයන්න)([\s!.]*|\s+ගන්න[\s!.]*)$/u.test(raw) ||
    /^(தொடங்கு|தேடு)[\s!.]*$/u.test(raw)
  );
}

export function looksLikeCareSeek(text: string): boolean {
  const raw = (text || '').trim();
  if (!raw) return false;
  if (looksLikeSearchLaunch(raw)) return true;
  return (
    /\b(caregiver|care[\s-]*giver|nurses?|carer|attendant|match me|vehmf)\b/i.test(raw) ||
    /\b(need|want)\s+(a\s+)?(someone|somebody|person)\b/i.test(raw) ||
    /\b(find|get|search(ing)?\s+for|look(ing)?\s+for)\s+(me\s+)?(a\s+)?(someone|somebody|person|care)\b/i.test(
      raw,
    ) ||
    /\bhelp\s+me\s+find\b/i.test(raw) ||
    /\b(start|begin|run)\s+(the\s+)?(search|match|matching|vehmf)\b/i.test(raw) ||
    /\b(search|match|find)\s+now\b/i.test(raw) ||
    /\bgo\s+ahead\s+(and\s+)?(search|match|find)\b/i.test(raw) ||
    /\bwho\s+can\s+(take\s*care|look\s*after|care\s+for|help)\b/i.test(raw) ||
    /\btake\s*care\s+of\s+(me|my|him|her|them|us)\b/i.test(raw) ||
    /පරිචාරක|பராமரிப்பாளர்|රැකබලා/.test(raw) ||
    /(හොය|සොය).{0,24}(කෙනෙක්|කෙනෙකු|පරිචාරක|caregiver|nurse)/.test(raw)
  );
}

/** Serah claimed a caregiver search is running (Gemini chat must not stall the UI). */
export function looksLikeSearchPromise(text: string): boolean {
  const raw = (text || '').trim();
  if (!raw) return false;
  return (
    /\bvehmf\b/i.test(raw) ||
    /\bi['’]?m on it\b/i.test(raw) ||
    /\blet you know\b/i.test(raw) ||
    /\bfinishes matching\b/i.test(raw) ||
    /\bresults are ready\b/i.test(raw) ||
    /\bsearch going\b/i.test(raw) ||
    /\bget that search\b/i.test(raw) ||
    /\blet['’]?s (get )?(that )?(search|match)\b/i.test(raw) ||
    /\bstart(ing)? (a |the )?search\b/i.test(raw) ||
    /\b(ranking|finding|searching)\s+(your\s+)?(best\s+)?(match|caregivers?)\b/i.test(raw)
  );
}

/** Keep the search stage up after a turn until cards arrive or we must clarify. */
export function shouldHoldMatchingUi(opts: {
  seeking: boolean;
  route?: string;
  situation?: string;
  reply?: string;
  hasMatch: boolean;
  clearMatch?: boolean;
  hasCondition: boolean;
}): boolean {
  if (opts.hasMatch || opts.clearMatch) return false;
  const situation = opts.situation || '';
  if (situation === 'goodbye' || situation === 'cancel' || situation === 'match_error') {
    return false;
  }
  const wantsSearch =
    opts.seeking ||
    opts.route === 'MATCH' ||
    opts.route === 'REFINE' ||
    looksLikeSearchPromise(opts.reply || '');
  return wantsSearch;
}

/** Wake Serah after goodbye / sleep. */
export function looksLikeWake(text: string): boolean {
  const raw = (text || '').trim();
  if (!raw) return false;
  const lower = raw.toLowerCase();
  if (/\b(hey|hi|hello)\s+serah\b/.test(lower) || /^serah\b/.test(lower)) return true;
  if (/හායි\s*සෙරා|ආයුබෝවන්\s*සෙරා|^සෙරා\b/.test(raw)) return true;
  if (/ஹாய்\s*சேரா|வணக்கம்\s*சேரா|^சேரா\b/.test(raw)) return true;
  return false;
}

/** Drop a leading wake phrase so the rest of the utterance can run as a turn. */
export function stripWakePrefix(text: string): string {
  return text
    .replace(/^(hey|hi|hello)\s+serah[,!.]?\s*/i, '')
    .replace(/^serah[,!.]?\s*/i, '')
    .replace(/^(හායි|ආයුබෝවන්)\s*සෙරා[,!.]?\s*/u, '')
    .replace(/^සෙරා[,!.]?\s*/u, '')
    .replace(/^(ஹாய்|வணக்கம்)\s*சேரா[,!.]?\s*/u, '')
    .replace(/^சேரா[,!.]?\s*/u, '')
    .trim();
}
