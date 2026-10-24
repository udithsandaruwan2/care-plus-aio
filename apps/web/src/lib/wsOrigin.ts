/** Origin for Care Plus sockets. Clients always append `/ws/...`. */
export function wsOrigin(fromEnv?: string): string {
  const raw = (fromEnv || '').trim();
  if (raw) {
    return raw.replace(/\/$/, '').replace(/\/ws$/i, '');
  }
  if (typeof window === 'undefined') return 'ws://127.0.0.1:8000';
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}`;
}
