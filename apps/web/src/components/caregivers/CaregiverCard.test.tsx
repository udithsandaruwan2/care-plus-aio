import type { CaregiverProfile } from '@care-plus/api-client';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';
import { CaregiverCard, caregiverSummary } from './CaregiverCard';

const base: CaregiverProfile = {
  id: 7,
  email: 'nimali@example.com',
  display_name: 'Nimali Fernando',
  longitude: 79.86,
  latitude: 6.93,
  city: 'Colombo',
  certifications: ['First Aid'],
  languages: ['Sinhala', 'English'],
  specialties: ['diabetes', 'elderly care'],
  care_levels: ['basic'],
  trust_score: 0.88,
  bio: 'Ten years supporting families with diabetes care at home.',
  age: 34,
  years_experience: 10,
  is_verified: true,
  review_count: 4,
  review_average: 4.5,
  is_available: true,
  photo_url: null,
};

function renderCard(overrides: Partial<CaregiverProfile> = {}) {
  return render(
    <MemoryRouter>
      <CaregiverCard caregiver={{ ...base, ...overrides }} />
    </MemoryRouter>,
  );
}

afterEach(() => cleanup());

describe('CaregiverCard', () => {
  it('shows the name, age, city and experience', () => {
    renderCard();
    expect(screen.getByRole('heading', { name: 'Nimali Fernando' })).toBeInTheDocument();
    expect(screen.getByText(/34 yrs · Colombo · 10 yrs exp/)).toBeInTheDocument();
  });

  it('links to the full profile for booking', () => {
    renderCard();
    expect(screen.getByRole('link', { name: /view profile/i })).toHaveAttribute(
      'href',
      '/caregivers/7',
    );
  });

  it('surfaces rating and verified state', () => {
    renderCard();
    expect(screen.getByText(/4\.5 \(4\)/)).toBeInTheDocument();
    expect(screen.getByText('Verified')).toBeInTheDocument();
  });

  it('falls back to initials when no photo is set', () => {
    renderCard();
    expect(screen.getByText('NF')).toBeInTheDocument();
  });

  it('marks unavailable caregivers', () => {
    renderCard({ is_available: false });
    expect(screen.getByText('Unavailable')).toBeInTheDocument();
  });

  it('says when a caregiver has no reviews', () => {
    renderCard({ review_count: 0, review_average: null });
    expect(screen.getByText('No reviews yet')).toBeInTheDocument();
  });
});

describe('caregiverSummary', () => {
  it('prefers the bio', () => {
    expect(caregiverSummary(base)).toBe(base.bio);
  });

  it('builds a blurb from specialties when the bio is empty', () => {
    expect(caregiverSummary({ ...base, bio: '' })).toBe(
      'Supports diabetes, elderly care around Colombo.',
    );
  });

  it('handles caregivers with no specialties or city', () => {
    expect(caregiverSummary({ ...base, bio: '', specialties: [], city: '' })).toBe(
      'Community caregiver on Care Plus.',
    );
  });
});
