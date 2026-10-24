import type { IntentDraft } from '@care-plus/core';
import type { MatchHit } from '@care-plus/api-client';

/** Personalized care-request note Serah types into the side card. */
export function composeRequestMessage(opts: {
  caregiverName: string;
  hit?: MatchHit | null;
  intent?: IntentDraft | null;
}): string {
  const name = (opts.caregiverName || 'there').trim() || 'there';
  const intent = opts.intent || {};
  const condition = (intent.condition || '').trim();
  const careLevel = (intent.care_level || '').trim();
  const language = (intent.language || '').trim();
  const specialties = (opts.hit?.specialties || []).slice(0, 2).join(', ');

  const need = [careLevel && `${careLevel} care`, condition && `for ${condition}`]
    .filter(Boolean)
    .join(' ');
  const lang = language ? ` We prefer care in ${language}.` : '';
  const skill = specialties ? ` Your ${specialties} background looks like a good fit.` : '';

  return (
    `Hello ${name}, I would like to request${need ? ` ${need}` : ' home care'}.` +
    `${lang}${skill} Please accept if you are available this week.`
  );
}
