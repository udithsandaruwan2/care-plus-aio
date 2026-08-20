import { createApiClient } from '@care-plus/api-client';
import { useConnectionStore } from './connectionStore';
import { clearTokens, getAccessToken, loadTokens, saveTokens } from './session';

export function getRefreshToken(): string | null {
  return loadTokens()?.refresh ?? null;
}

export const api = createApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
  getAccessToken,
  getRefreshToken,
  timeoutMs: 30_000,
  maxRetries: 2,
  onTokensRefreshed: ({ access, refresh }) => {
    const prev = loadTokens();
    saveTokens({
      access,
      refresh: refresh || prev?.refresh || '',
    });
  },
  onAuthFailure: () => {
    clearTokens();
  },
  onRequestOutcome: (outcome) => {
    useConnectionStore.getState().noteRequestOutcome(outcome);
  },
});
