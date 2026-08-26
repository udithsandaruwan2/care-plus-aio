import type { CaregiverDetail } from '@care-plus/api-client';
import type { ProfileNarrateMode } from './store';

export type { ProfileNarrateMode };

/**
 * Short spoken blurb for Serah TTS — not a full page scrape.
 * ``brief`` for view_profile; ``detail`` for describe_caregiver.
 */
export function caregiverSpokenSummary(
  profile: CaregiverDetail,
  mode: ProfileNarrateMode = 'brief',
): string {
  const name = profile.display_name?.trim() || 'This caregiver';
  const area =
    (profile.approximate_area || profile.city || '').trim() || 'Sri Lanka';
  const langs = (profile.languages || []).filter(Boolean);
  const skills = (profile.specialties || []).filter(Boolean).slice(0, 4);
  const careLevels = (profile.care_levels || []).filter(Boolean);
  const rating =
    profile.review_count && profile.review_average != null
      ? `${profile.review_average.toFixed(1)} out of 5 from ${profile.review_count} review${
          profile.review_count === 1 ? '' : 's'
        }`
      : 'no reviews yet';
  const verified = profile.is_verified ? ' They are verified on Care Plus.' : '';
  const experience =
    profile.years_experience != null && profile.years_experience > 0
      ? ` with ${profile.years_experience} years of experience`
      : '';

  if (mode === 'brief') {
    const skillBit = skills.length ? ` Skills include ${skills.join(', ')}.` : '';
    const langBit = langs.length ? ` Languages: ${langs.join(', ')}.` : '';
    return `${name} is based around ${area}${experience}. Rating: ${rating}.${langBit}${skillBit}${verified} Say send the request if you want me to hire them, or ask me to tell you more.`;
  }

  const bio = (profile.bio || '').trim();
  const bioBit = bio
    ? ` ${bio.length > 220 ? `${bio.slice(0, 217).trimEnd()}…` : bio}`
    : '';
  const skillBit = skills.length
    ? ` Specialties: ${skills.join(', ')}.`
    : ' Specialties are not listed yet.';
  const langBit = langs.length
    ? ` They speak ${langs.join(', ')}.`
    : '';
  const levelBit = careLevels.length
    ? ` Care levels: ${careLevels.join(', ')}.`
    : '';
  const certs = (profile.certifications || []).filter(Boolean).slice(0, 3);
  const certBit = certs.length ? ` Certifications: ${certs.join(', ')}.` : '';

  return `${name}, around ${area}${experience}. Rating: ${rating}.${langBit}${skillBit}${levelBit}${certBit}${verified}${bioBit} Would you like me to send a care request?`;
}
