import { createApiClient, type ApiClient } from "@care-plus/api-client";

const ACCESS_KEY = "careplus_agent_access";
const REFRESH_KEY = "careplus_agent_refresh";

export function getAccessToken(): string | null {
  try {
    return sessionStorage.getItem(ACCESS_KEY);
  } catch {
    return null;
  }
}

export function getRefreshToken(): string | null {
  try {
    return sessionStorage.getItem(REFRESH_KEY);
  } catch {
    return null;
  }
}

export function saveTokens(access: string, refresh?: string): void {
  sessionStorage.setItem(ACCESS_KEY, access);
  if (refresh) sessionStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  sessionStorage.removeItem(ACCESS_KEY);
  sessionStorage.removeItem(REFRESH_KEY);
}

/** Prefer same-origin proxy in dev so cookies/CORS stay simple. */
const baseUrl =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";

export const api: ApiClient = createApiClient({
  baseUrl,
  getAccessToken,
  getRefreshToken,
  timeoutMs: 90_000,
  maxRetries: 1,
  onTokensRefreshed: ({ access, refresh }) => {
    saveTokens(access, refresh);
  },
  onAuthFailure: () => {
    clearTokens();
  },
});
