import type { SerahAction } from '@care-plus/api-client';

const VIEW =
  /\b(view|show|open|see|check|review|look\s*at)\b[\s\S]{0,40}\b(profile|details?)\b/i;
const REQUEST =
  /\b((send|submit)\s+(the\s+)?(care\s+)?request|send\s+it|request(\s+(care|them|him|her|this|that|the|the\s+caregiver))?|hire(\s+\w+)?|book(ing)?(\s+(the|this|that|a))?\s*(caregiver|carer|nurse|them|him|her|this(\s+one)?)?|book\s+(them|him|her|the\s+(first|top|caregiver)))\b/i;
const SCHEDULE =
  /\b((open|show|see|view)\s+(the\s+)?(schedule|calendar|availability|slots?)|(schedule|book)\s+(a\s+)?(visit|shift|slot|time|appointment)|available\s+(times?|slots?))\b/i;
const OPENING_PROFILE = /\bopening\b[\s\S]{0,80}\bprofile\b/i;

const NAME_STRIP =
  /\b(please|thanks|thank\s*you|review|check|open|show|see|view|look\s*at|read|i|i'?m|i'?d|to|of|for|from|with|and|or|can|you|me|my|want|would|like|assist|his|her|their|the|a|an|this|that|profile|details?|bio|caregiver|nurse|carer|request|book|hire|send|choose|select|tell\s*me\s*more|describe|about|number|rank|first|second|third|fourth|fifth|top|1st|2nd|3rd|4th|5th|opening)\b|[^\w\s'-]/gi;

function parseRank(text: string): number | null {
  const num = text.match(/(?:#|number|no\.?|rank)\s*(\d+)/i);
  if (num) return Number(num[1]);
  if (/\b(first|top|1st)\b/i.test(text)) return 1;
  if (/\b(second|2nd)\b/i.test(text)) return 2;
  if (/\b(third|3rd)\b/i.test(text)) return 3;
  return null;
}

function parseName(text: string): string {
  const cleaned = (text || '')
    .replace(NAME_STRIP, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^[-']+|[-']+$/g, '');
  if (cleaned.length < 2) return '';
  if (/^(yes|yeah|yep|ok|okay|sure|him|her|them)$/i.test(cleaned)) return '';
  return cleaned;
}

/** Local fallback when Live Gemini chats without calling serah_voice_turn. */
export function inferPostMatchAction(text: string): SerahAction | null {
  const raw = (text || '').trim();
  if (!raw) return null;
  const rank = parseRank(raw);
  const name_query = parseName(raw);
  if (VIEW.test(raw) || OPENING_PROFILE.test(raw)) {
    return { type: 'view_profile', rank, name_query, caregiver_id: null };
  }
  if (/\b(profile|පැතිකඩ|சுயவிவரம்)\b/i.test(raw) && /\b(show|view|open|see)\b/i.test(raw)) {
    return { type: 'view_profile', rank, name_query, caregiver_id: null };
  }
  if (SCHEDULE.test(raw)) {
    return { type: 'book_shift', rank, name_query, caregiver_id: null };
  }
  if (REQUEST.test(raw)) {
    return { type: 'request', rank, name_query, caregiver_id: null };
  }
  return null;
}
