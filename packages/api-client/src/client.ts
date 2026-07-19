import {
  ConsentRow,
  ConsentState,
  HealthResponse,
  MatchResponse,
  RegisterResponse,
  TokenPair,
  User,
  VoiceIntent,
  type MatchInput,
  type RegisterInput,
  type VoiceIntentInput,
} from './schemas';

export type ApiClientOptions = {
  baseUrl: string;
  getAccessToken?: () => string | null;
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
  const { baseUrl, getAccessToken } = options;

  async function request<T>(
    path: string,
    init: RequestInit = {},
    parse: (data: unknown) => T,
  ): Promise<T> {
    const headers = new Headers(init.headers);
    if (!headers.has('Content-Type') && init.body) {
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
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
