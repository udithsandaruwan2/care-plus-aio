import { create } from 'zustand';

export type ConnectionKind = 'online' | 'offline' | 'degraded';

type ConnectionState = {
  browserOnline: boolean;
  requestDegraded: boolean;
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
  kind: typeof navigator === 'undefined' || navigator.onLine ? 'online' : 'offline',
  setBrowserOnline: (online) => {
    const requestDegraded = get().requestDegraded;
    set({
      browserOnline: online,
      requestDegraded: online ? requestDegraded : false,
      kind: derive(online, online ? requestDegraded : false),
    });
  },
  noteRequestOutcome: (outcome) => {
    const browserOnline = get().browserOnline;
    if (outcome === 'ok') {
      set({ requestDegraded: false, kind: derive(browserOnline, false) });
      return;
    }
    if (outcome === 'network' || outcome === 'timeout') {
      set({ requestDegraded: true, kind: derive(browserOnline, true) });
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
