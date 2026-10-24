import { create } from 'zustand';

export type ConnectionKind = 'online' | 'offline' | 'degraded';

type ConnectionState = {
  browserOnline: boolean;
  requestDegraded: boolean;
  /** Consecutive transport failures. Banner only after 2 — a slow voice turn is not offline. */
  failures: number;
  kind: ConnectionKind;
  setBrowserOnline: (online: boolean) => void;
  noteRequestOutcome: (outcome: 'ok' | 'network' | 'timeout' | 'http') => void;
};

function derive(browserOnline: boolean, requestDegraded: boolean): ConnectionKind {
  if (!browserOnline) return 'offline';
  if (requestDegraded) return 'degraded';
  return 'online';
}

export const useConnectionStore = create<ConnectionState>((set, get) => ({
  browserOnline: typeof navigator === 'undefined' ? true : navigator.onLine,
  requestDegraded: false,
  failures: 0,
  kind: typeof navigator === 'undefined' || navigator.onLine ? 'online' : 'offline',
  setBrowserOnline: (online) => {
    const requestDegraded = online ? get().requestDegraded : false;
    set({
      browserOnline: online,
      requestDegraded,
      failures: online ? get().failures : 0,
      kind: derive(online, requestDegraded),
    });
  },
  noteRequestOutcome: (outcome) => {
    const browserOnline = get().browserOnline;
    if (outcome === 'ok' || outcome === 'http') {
      set({ failures: 0, requestDegraded: false, kind: derive(browserOnline, false) });
      return;
    }
    if (outcome === 'network' || outcome === 'timeout') {
      const failures = get().failures + 1;
      const requestDegraded = failures >= 2;
      set({ failures, requestDegraded, kind: derive(browserOnline, requestDegraded) });
    }
  },
}));

/** Bind window online/offline once (call from AppShell or AuthProvider). */
export function bindConnectionListeners(): () => void {
  if (typeof window === 'undefined') return () => undefined;
  const on = () => useConnectionStore.getState().setBrowserOnline(true);
  const off = () => useConnectionStore.getState().setBrowserOnline(false);
  window.addEventListener('online', on);
  window.addEventListener('offline', off);
  useConnectionStore.getState().setBrowserOnline(navigator.onLine);
  return () => {
    window.removeEventListener('online', on);
    window.removeEventListener('offline', off);
  };
}
