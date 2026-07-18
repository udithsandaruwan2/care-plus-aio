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
import { ApiError } from '@care-plus/api-client';
import { api } from './api';
import { clearTokens, loadTokens, saveTokens } from './session';

type AuthState = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, role: 'patient' | 'caregiver') => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshMe = useCallback(async () => {
    const tokens = loadTokens();
    if (!tokens) {
      setUser(null);
      return;
    }
    try {
      const me = await api.me();
      setUser(me);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        clearTokens();
      }
      setUser(null);
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
  }, []);

  const register = useCallback(
    async (email: string, password: string, role: 'patient' | 'caregiver') => {
      await api.register({ email, password, role });
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout }),
    [user, loading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
