import { describe, expect, it } from 'vitest';
import type { CaregiverDetail } from '@care-plus/api-client';
import { caregiverSpokenSummary } from './caregiverSpokenSummary';

const base: CaregiverDetail = {
  id: 7,
  email: 'asha@example.com',
  display_name: 'Asha Perera',
  longitude: null,
  latitude: null,
  city: 'Colombo',
  approximate_area: 'Colombo 5',
  certifications: ['First Aid'],
  languages: ['English', 'Sinhala'],
  specialties: ['fever', 'elderly care'],
  care_levels: ['basic', 'intermediate'],
  trust_score: 0.82,
  bio: 'Experienced community caregiver focused on fever and recovery support.',
  age: 34,
  years_experience: 8,
  is_verified: true,
  review_count: 12,
  review_average: 4.6,
  is_available: true,
  photo_url: null,
  reviews_teaser: [],
};

describe('caregiverSpokenSummary', () => {
  it('builds a brief summary for view_profile', () => {
    const text = caregiverSpokenSummary(base, 'brief');
    expect(text).toContain('Asha Perera');
    expect(text).toContain('Colombo 5');
    expect(text).toContain('4.6 out of 5');
    expect(text).toContain('English');
    expect(text).toContain('fever');
    expect(text).toContain('send the request');
    expect(text).not.toContain('Experienced community caregiver');
  });

  it('includes bio and more fields for describe_caregiver', () => {
    const text = caregiverSpokenSummary(base, 'detail');
    expect(text).toContain('Experienced community caregiver');
    expect(text).toContain('Care levels');
    expect(text).toContain('First Aid');
    expect(text).toContain('Would you like me to send a care request');
  });
});
