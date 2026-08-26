import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { CaregiverDetail } from '@care-plus/api-client';
import { CaregiverProfileDrawer } from './CaregiverProfileDrawer';
import { useAssistant } from './store';

const detail: CaregiverDetail = {
  id: 7,
  email: 'asha@example.com',
  display_name: 'Asha Perera',
  longitude: null,
  latitude: null,
  city: 'Colombo',
  approximate_area: 'Colombo 5',
  certifications: ['First Aid'],
  languages: ['English'],
  specialties: ['fever'],
  care_levels: ['basic'],
  trust_score: 0.8,
  bio: 'Warm caregiver for fever recovery.',
  age: 34,
  years_experience: 5,
  is_verified: true,
  review_count: 3,
  review_average: 4.5,
  is_available: true,
  photo_url: null,
  reviews_teaser: [],
};

vi.mock('../auth/api', () => ({
  api: {
    caregiver: vi.fn(async () => detail),
  },
}));

vi.mock('./useTts', () => ({
  isSerahSpeaking: () => false,
  speakSerah: vi.fn(async () => undefined),
  subscribeSerahSpeaking: () => () => undefined,
}));

describe('CaregiverProfileDrawer', () => {
  beforeEach(() => {
    cleanup();
    useAssistant.getState().reset();
  });

  it('stays closed until a caregiver is focused', () => {
    render(
      <MemoryRouter>
        <CaregiverProfileDrawer />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId('serah-profile-drawer')).toBeNull();
  });

  it('opens and loads detail when view_profile sets focus', async () => {
    const { api } = await import('../auth/api');
    useAssistant.getState().setFocusedCaregiverId(7);
    useAssistant.getState().setBookingStage('profile');
    useAssistant.getState().setProfileNarrateMode('brief');

    render(
      <MemoryRouter>
        <CaregiverProfileDrawer />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('serah-profile-drawer')).toBeTruthy();
    await waitFor(() => {
      expect(api.caregiver).toHaveBeenCalledWith(7);
      expect(screen.getByRole('heading', { name: 'Asha Perera' })).toBeTruthy();
    });
    expect(screen.getByText(/Warm caregiver for fever recovery/)).toBeTruthy();
    expect(screen.getByRole('link', { name: /Open full profile page/i })).toHaveAttribute(
      'href',
      '/caregivers/7',
    );
  });
});
