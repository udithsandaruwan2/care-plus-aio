import {
  CaregiverDetail,
  CaregiverListResponse,
  CaregiverProfile,
  ConsentRow,
  ConsentState,
  HealthResponse,
  MatchResponse,
  RegisterResponse,
  TokenPair,
  User,
  VoiceIntent,
  VoiceSessionClearResponse,
  VoiceSessionResponse,
  VoiceTurnResponse,
  DialoguePolicy,
  type CaregiverListParams,
  type MatchInput,
  type RegisterInput,
  type VoiceIntentInput,
} from './schemas';

export type ApiClientOptions = {
  baseUrl: string;
  getAccessToken?: () => string | null;
  getRefreshToken?: () => string | null;
  /** Called after a successful token refresh (access, and refresh if rotated). */
  onTokensRefreshed?: (tokens: { access: string; refresh?: string }) => void;
  /** Called when refresh fails — clear session / redirect to login. */
  onAuthFailure?: () => void;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function createApiClient(options: ApiClientOptions) {
  const { baseUrl, getAccessToken, getRefreshToken, onTokensRefreshed, onAuthFailure } = options;
  let refreshInFlight: Promise<string | null> | null = null;

  async function refreshAccessToken(): Promise<string | null> {
    if (refreshInFlight) return refreshInFlight;
    refreshInFlight = (async () => {
      const refresh = getRefreshToken?.();
      if (!refresh) return null;
      try {
        const res = await fetch(`${baseUrl.replace(/\/$/, '')}/auth/token/refresh/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh }),
        });
        const text = await res.text();
        let data: unknown = null;
        if (text) {
          try {
            data = JSON.parse(text);
          } catch {
            data = text;
          }
        }
        if (!res.ok) {
          onAuthFailure?.();
          return null;
        }
        // Refresh may return only { access } unless rotation is enabled.
        const access =
          data && typeof data === 'object' && 'access' in data
            ? String((data as { access: unknown }).access)
            : '';
        if (!access) {
          onAuthFailure?.();
          return null;
        }
        const nextRefresh =
          data && typeof data === 'object' && 'refresh' in data
            ? String((data as { refresh: unknown }).refresh)
            : undefined;
        onTokensRefreshed?.({ access, refresh: nextRefresh });
        return access;
      } catch {
        onAuthFailure?.();
        return null;
      } finally {
        refreshInFlight = null;
      }
    })();
    return refreshInFlight;
  }

  async function request<T>(
    path: string,
    init: RequestInit = {},
    parse: (data: unknown) => T,
    retried = false,
  ): Promise<T> {
    const headers = new Headers(init.headers);
    if (!headers.has('Content-Type') && init.body && !(init.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }
    const token = getAccessToken?.();
    if (token) headers.set('Authorization', `Bearer ${token}`);

    const res = await fetch(`${baseUrl.replace(/\/$/, '')}${path}`, {
      ...init,
      headers,
    });
    const text = await res.text();
    let data: unknown = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = text;
      }
    }
    if (res.status === 401 && !retried && getRefreshToken && !path.includes('/auth/token')) {
      const next = await refreshAccessToken();
      if (next) {
        return request(path, init, parse, true);
      }
    }
    if (!res.ok) {
      throw new ApiError(`HTTP ${res.status}`, res.status, data);
    }
    return parse(data);
  }

  return {
    health: () => request('/health/', {}, (d) => HealthResponse.parse(d)),
    me: () => request('/auth/me/', {}, (d) => User.parse(d)),
    login: (email: string, password: string) =>
      request('/auth/token/', { method: 'POST', body: JSON.stringify({ email, password }) }, (d) =>
        TokenPair.parse(d),
      ),
    register: (input: RegisterInput) =>
      request(
        '/auth/register/',
        {
          method: 'POST',
          body: JSON.stringify({
            email: input.email,
            password: input.password,
            role: input.role ?? 'patient',
            first_name: input.first_name ?? '',
            last_name: input.last_name ?? '',
          }),
        },
        (d) => RegisterResponse.parse(d),
      ),
    voiceIntent: (input: VoiceIntentInput) =>
      request(
        '/voice/intent/',
        {
          method: 'POST',
          body: JSON.stringify({
            text: input.text,
            ...(input.language ? { language: input.language } : {}),
          }),
        },
        (d) => VoiceIntent.parse(d),
      ),
    /**
     * Conversational turn: optional Web Speech text + recorded audio.
     * Audio is preferred for Sinhala/Tamil (server Whisper ASR).
     * ``uiLanguage`` locks ASR + Serah reply language.
     */
    voiceTurn: (input: {
      text?: string;
      audio?: Blob | null;
      hasPriorMatch?: boolean;
      priorIntent?: Record<string, unknown> | null;
      priorMatch?: Record<string, unknown> | null;
      uiLanguage?: 'Sinhala' | 'Tamil' | 'English';
    }) => {
      const form = new FormData();
      if (input.text) form.append('text', input.text);
      if (input.audio) form.append('audio', input.audio, 'turn.webm');
      form.append('has_prior_match', input.hasPriorMatch ? 'true' : 'false');
      if (input.priorIntent) form.append('prior_intent', JSON.stringify(input.priorIntent));
      if (input.priorMatch) form.append('prior_match', JSON.stringify(input.priorMatch));
      if (input.uiLanguage) form.append('ui_language', input.uiLanguage);
      return request(
        '/voice/turn/',
        {
          method: 'POST',
          body: form,
          headers: {}, // let browser set multipart boundary
        },
        (d) => VoiceTurnResponse.parse(d),
      );
    },
    voiceSession: () =>
      request('/voice/session/', {}, (d) => VoiceSessionResponse.parse(d)),
    clearVoiceSession: () =>
      request(
        '/voice/session/clear/',
        { method: 'POST', body: JSON.stringify({}) },
        (d) => VoiceSessionClearResponse.parse(d),
      ),
    dialoguePolicy: () =>
      request('/voice/policy/', {}, (d) => DialoguePolicy.parse(d)),
    getConsent: () => request('/consent/', {}, (d) => ConsentState.parse(d)),
    setConsent: (scope: string, granted: boolean) =>
      request('/consent/', { method: 'POST', body: JSON.stringify({ scope, granted }) }, (d) =>
        ConsentRow.parse(d),
      ),
    match: (input: MatchInput) =>
      request(
        '/match/',
        {
          method: 'POST',
          body: JSON.stringify({
            condition: input.condition ?? '',
            language: input.language ?? '',
            care_level: input.care_level ?? '',
            query: input.query ?? '',
            ...(input.longitude != null && input.latitude != null
              ? { longitude: input.longitude, latitude: input.latitude }
              : {}),
            ...(input.k != null ? { k: input.k } : {}),
            ...(input.emergency != null ? { emergency: input.emergency } : {}),
          }),
        },
        (d) => MatchResponse.parse(d),
      ),
    caregivers: (params: CaregiverListParams = {}) => {
      const qs = new URLSearchParams();
      if (params.q) qs.set('q', params.q);
      if (params.language) qs.set('language', params.language);
      if (params.specialty) qs.set('specialty', params.specialty);
      if (params.city) qs.set('city', params.city);
      if (params.care_level) qs.set('care_level', params.care_level);
      if (params.available != null) qs.set('available', String(params.available));
      if (params.near) qs.set('near', params.near);
      if (params.radius_km != null) qs.set('radius_km', String(params.radius_km));
      if (params.page != null) qs.set('page', String(params.page));
      if (params.page_size != null) qs.set('page_size', String(params.page_size));
      const suffix = qs.toString() ? `?${qs}` : '';
      return request(`/caregivers/${suffix}`, {}, (d) => CaregiverListResponse.parse(d));
    },
    caregiver: (id: number) =>
      request(`/caregivers/${id}/`, {}, (d) => CaregiverDetail.parse(d)),
    myCaregiverProfile: () =>
      request('/caregivers/me/', {}, (d) => CaregiverProfile.parse(d)),
    setMyAvailability: (is_available: boolean) =>
      request(
        '/caregivers/me/',
        {
          method: 'PATCH',
          body: JSON.stringify({ is_available }),
        },
        (d) => CaregiverProfile.parse(d),
      ),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
