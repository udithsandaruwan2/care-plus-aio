import * as SecureStore from 'expo-secure-store';

const ACCESS_KEY = 'cp_access';
const REFRESH_KEY = 'cp_refresh';

export type StoredTokens = {
  access: string;
  refresh: string;
};

/** In-memory cache so the API client can read tokens synchronously. */
let memory: StoredTokens | null = null;

export function getAccessToken(): string | null {
  return memory?.access ?? null;
}

export function getRefreshToken(): string | null {
  return memory?.refresh ?? null;
}

export function peekTokens(): StoredTokens | null {
  return memory;
}

export async function loadTokens(): Promise<StoredTokens | null> {
  const access = await SecureStore.getItemAsync(ACCESS_KEY);
  const refresh = await SecureStore.getItemAsync(REFRESH_KEY);
  if (!access || !refresh) {
    memory = null;
    return null;
  }
  memory = { access, refresh };
  return memory;
}

export async function saveTokens(tokens: StoredTokens): Promise<void> {
  memory = tokens;
  await SecureStore.setItemAsync(ACCESS_KEY, tokens.access);
  await SecureStore.setItemAsync(REFRESH_KEY, tokens.refresh);
}

export async function clearTokens(): Promise<void> {
  memory = null;
  await SecureStore.deleteItemAsync(ACCESS_KEY);
  await SecureStore.deleteItemAsync(REFRESH_KEY);
}
