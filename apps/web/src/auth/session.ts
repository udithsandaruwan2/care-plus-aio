import type { User } from '@care-plus/api-client';

const ACCESS_KEY = 'cp_access';
const REFRESH_KEY = 'cp_refresh';
const USER_KEY = 'cp_user';

export type StoredTokens = {
  access: string;
  refresh: string;
};

export function loadTokens(): StoredTokens | null {
  const access = localStorage.getItem(ACCESS_KEY);
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (!access || !refresh) return null;
  return { access, refresh };
}

export function saveTokens(tokens: StoredTokens): void {
  localStorage.setItem(ACCESS_KEY, tokens.access);
  localStorage.setItem(REFRESH_KEY, tokens.refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  clearCachedUser();
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

/** Last known profile so offline reload can keep the user signed in (Step 82). */
export function saveCachedUser(user: User): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function loadCachedUser(): User | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function clearCachedUser(): void {
  localStorage.removeItem(USER_KEY);
}
