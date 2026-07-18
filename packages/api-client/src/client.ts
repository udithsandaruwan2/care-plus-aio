import { HealthResponse, type TokenPair, User } from './schemas';

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
    const data = text ? JSON.parse(text) : null;
    if (!res.ok) {
      throw new ApiError(`HTTP ${res.status}`, res.status, data);
    }
    return parse(data);
  }

  return {
    health: () => request('/health/', {}, (d) => HealthResponse.parse(d)),
    me: () => request('/auth/me/', {}, (d) => User.parse(d)),
    login: (email: string, password: string) =>
      request(
        '/auth/token/',
        { method: 'POST', body: JSON.stringify({ email, password }) },
        (d) => d as TokenPair,
      ),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
