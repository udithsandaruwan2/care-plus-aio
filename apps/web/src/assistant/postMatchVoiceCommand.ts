import type { SerahAction } from '@care-plus/api-client';

const VIEW =
  /\b(view|show|open|see|check|review|look\s*at)\b[\s\S]{0,40}\b(profile|details?)\b/i;
const REQUEST =
  /\b((send|submit)\s+(the\s+)?(care\s+)?request|send\s+it|request(\s+(care|them|him|her|this|that|the|the\s+caregiver))?|hire(\s+\w+)?|book(ing)?(\s+(the|this|that|a))?\s*(caregiver|carer|nurse|them|him|her|this(\s+one)?)?|book\s+(them|him|her|the\s+(first|top|caregiver)))\b/i;
const SCHEDULE =
  /\b((open|show|see|view)\s+(the\s+)?(schedule|calendar|availability|slots?)|(schedule|book)\s+(a\s+)?(visit|shift|slot|time|appointment)|available\s+(times?|slots?))\b/i;

function parseRank(text: string): number | null {
  const num = text.match(/(?:#|number|no\.?|rank)\s*(\d+)/i);
  if (num) return Number(num[1]);
  if (/\b(first|top|1st)\b/i.test(text)) return 1;
  if (/\b(second|2nd)\b/i.test(text)) return 2;
  if (/\b(third|3rd)\b/i.test(text)) return 3;
  return null;
}

function parseName(text: string): string {
  const named = text.match(
    /\b(?:profile|details?|request|schedule|hire)\s+(?:for\s+|of\s+)?([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)?)/,
  );
  return named?.[1]?.trim() || '';
}

/** Local fallback when Live Gemini chats without calling serah_voice_turn. */
export function inferPostMatchAction(text: string): SerahAction | null {
  const raw = (text || '').trim();
  if (!raw) return null;
  const rank = parseRank(raw);
  const name_query = parseName(raw);
  if (VIEW.test(raw) || /\b(profile|පැතිකඩ|சுயவிவரம்)\b/i.test(raw)) {
    if (VIEW.test(raw) || /\b(show|view|open|see)\b/i.test(raw)) {
      return { type: 'view_profile', rank, name_query, caregiver_id: null };
    }
  }
  if (SCHEDULE.test(raw)) {
    return { type: 'book_shift', rank, name_query, caregiver_id: null };
  }
  if (REQUEST.test(raw)) {
    return { type: 'request', rank, name_query, caregiver_id: null };
  }
  return null;
}
