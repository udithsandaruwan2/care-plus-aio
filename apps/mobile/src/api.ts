import { createApiClient } from '@care-plus/api-client';
import Constants from 'expo-constants';

/**
 * API base URL for the lean Docker backend (`/api/v1`).
 * Override with EXPO_PUBLIC_API_URL (e.g. http://10.0.2.2:8000/api/v1 for Android emulator).
 */
function resolveBaseUrl(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL?.trim();
  if (fromEnv) return fromEnv.replace(/\/$/, '');

  const hostUri =
    Constants.expoConfig?.hostUri ??
    Constants.experienceUrl?.replace(/^exp:\/\//, '') ??
    '';
  const host = hostUri.split(':')[0];
  if (host && host !== 'localhost' && host !== '127.0.0.1') {
    return `http://${host}:8000/api/v1`;
  }
  return 'http://127.0.0.1:8000/api/v1';
}

export const apiBaseUrl = resolveBaseUrl();

export const api = createApiClient({
  baseUrl: apiBaseUrl,
});
