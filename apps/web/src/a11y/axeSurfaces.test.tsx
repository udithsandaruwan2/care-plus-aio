import type { ReactElement, ReactNode } from 'react';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import type { MatchResponse } from '@care-plus/api-client';
import { MatchResultCards } from '../assistant/MatchResultCards';
import { LocaleProvider } from '../i18n/LocaleProvider';
import { LoginPage } from '../pages/LoginPage';
import { PrivacyNoticePage } from '../pages/PrivacyNoticePage';
import { PublicHomePage } from '../pages/PublicHomePage';
import { RegisterPage } from '../pages/RegisterPage';
import { ThemeProvider } from '../theme/ThemeProvider';

vi.mock('../auth/api', () => ({
  api: {
    me: vi.fn(async () => {
      throw new Error('unauthorized');
    }),
    login: vi.fn(),
    register: vi.fn(),
    createCareRequest: vi.fn(),
  },
}));

vi.mock('../auth/AuthContext', () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => children,
  useAuth: () => ({
    user: null,
    loading: false,
    sessionStale: false,
    login: async () => undefined,
    register: async () => undefined,
    logout: () => undefined,
  }),
}));

vi.mock('../assistant/store', () => ({
  useAssistant: Object.assign(
    () => ({
      setState: vi.fn(),
      setInterim: vi.fn(),
      appendTranscript: vi.fn(),
      reset: vi.fn(),
    }),
    {
      getState: () => ({
        setState: vi.fn(),
        setInterim: vi.fn(),
        appendTranscript: vi.fn(),
        reset: vi.fn(),
        transcript: '',
      }),
    },
  ),
}));

vi.mock('../assistant/useTts', () => ({
  speakSerah: vi.fn(async () => undefined),
  stopSpeaking: vi.fn(),
  subscribeSerahSpeaking: vi.fn(() => () => undefined),
  isSerahSpeaking: vi.fn(() => false),
}));

function wrap(ui: ReactElement) {
  return render(
    <ThemeProvider>
      <LocaleProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </LocaleProvider>
    </ThemeProvider>,
  );
}

const sampleMatch: MatchResponse = {
  request_id: 1,
  query: 'diabetes Sinhala',
  latency_ms: 42,
  emergency: false,
  refined: false,
  weights: { cbf: 0.48, cf: 0.07, geo: 0.2, trust: 0.25 },
  results: [
    {
      caregiver_id: 7,
      rank: 1,
      score: 0.91,
      display_name: 'Nimal Perera',
      languages: ['Sinhala', 'English'],
      specialties: ['diabetes'],
      care_levels: ['intermediate'],
      trust_score: 0.88,
      is_available: true,
      distance_m: 3200,
      breakdown: { cbf: 0.9, cf: 0.4, geo: 0.8, trust: 0.88 },
      explanation: 'Matched because: strong medical/skill match.',
      previous_rank: null,
      rank_delta: null,
    },
  ],
};

describe('axe: auth + home + results', () => {
  it('PublicHomePage has no serious axe violations', async () => {
    const { container } = wrap(<PublicHomePage />);
    const results = await axe(container, {
      rules: { region: { enabled: false } },
    });
    expect(results).toHaveNoViolations();
  });

  it('LoginPage has no serious axe violations', async () => {
    const { container } = wrap(<LoginPage />);
    const results = await axe(container, {
      rules: { region: { enabled: false } },
    });
    expect(results).toHaveNoViolations();
  });

  it('PrivacyNoticePage has no serious axe violations', async () => {
    const { container } = wrap(<PrivacyNoticePage />);
    const results = await axe(container, {
      rules: { region: { enabled: false } },
    });
    expect(results).toHaveNoViolations();
  });

  it('RegisterPage has no serious axe violations', async () => {
    const { container } = wrap(<RegisterPage />);
    const results = await axe(container, {
      rules: { region: { enabled: false } },
    });
    expect(results).toHaveNoViolations();
  });

  it('MatchResultCards has no serious axe violations', async () => {
    const { container } = wrap(
      <MatchResultCards match={sampleMatch} canRequestCare uiLanguage="English" />,
    );
    const results = await axe(container, {
      rules: { region: { enabled: false } },
    });
    expect(results).toHaveNoViolations();
  });
});
