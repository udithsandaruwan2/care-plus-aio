import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { User } from '@care-plus/api-client';
import { ApiError, isNetworkError } from '@care-plus/api-client';
import { api } from './api';
import { bindConnectionListeners, useConnectionStore } from './connectionStore';
import { clearTokens, loadCachedUser, loadTokens, saveCachedUser, saveTokens } from './session';

type AuthState = {
  user: User | null;
  loading: boolean;
  /** True when tokens exist but the last /me refresh failed due to transport. */
  sessionStale: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (email: string, password: string, role: 'patient' | 'caregiver') => Promise<User>;
  logout: () => void;
  requestOtp: () => Promise<{
    detail: string;
    expires_in?: number;
    demo?: boolean;
    demo_code?: string;
  }>;
  verifyOtp: (code: string) => Promise<User>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => loadCachedUser());
  const [loading, setLoading] = useState(true);
  const [sessionStale, setSessionStale] = useState(false);

  useEffect(() => bindConnectionListeners(), []);

  const refreshMe = useCallback(async () => {
    const tokens = loadTokens();
    if (!tokens) {
      setUser(null);
      setSessionStale(false);
      return;
    }
    try {
      const me = await api.me();
      setUser(me);
      saveCachedUser(me);
      setSessionStale(false);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        clearTokens();
        setUser(null);
        setSessionStale(false);
        return;
      }
      // Network / timeout / unexpected — keep last known user when possible.
      const cached = loadCachedUser();
      if (cached) {
        setUser(cached);
        setSessionStale(true);
        if (isNetworkError(err)) {
          useConnectionStore.getState().noteRequestOutcome('network');
        }
        return;
      }
      setUser(null);
      setSessionStale(Boolean(tokens));
    }
  }, []);

  useEffect(() => {
    refreshMe().finally(() => setLoading(false));
  }, [refreshMe]);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api.login(email, password);
    saveTokens(tokens);
    const me = await api.me();
    setUser(me);
    saveCachedUser(me);
    setSessionStale(false);
    return me;
  }, []);

  const register = useCallback(
    async (email: string, password: string, role: 'patient' | 'caregiver') => {
      await api.register({ email, password, role });
      return login(email, password);
    },
    [login],
  );

  const requestOtp = useCallback(() => api.requestOtp(), []);

  const verifyOtp = useCallback(async (code: string) => {
    const tokens = await api.verifyOtp(code);
    saveTokens(tokens);
    const me = await api.me();
    setUser(me);
    saveCachedUser(me);
    setSessionStale(false);
    return me;
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    setSessionStale(false);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      sessionStale,
      login,
      register,
      logout,
      requestOtp,
      verifyOtp,
    }),
    [user, loading, sessionStale, login, register, logout, requestOtp, verifyOtp],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
