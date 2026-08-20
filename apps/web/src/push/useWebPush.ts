import { useCallback, useEffect, useState } from 'react';
import { api } from '../auth/api';

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = window.atob(base64);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i);
  return output;
}

export type WebPushState = {
  supported: boolean;
  permission: NotificationPermission | 'unsupported';
  subscribed: boolean;
  configured: boolean;
  busy: boolean;
  error: string | null;
  enable: () => Promise<void>;
  disable: () => Promise<void>;
};

/** Register service worker + subscribe to VAPID push when the user grants permission. */
export function useWebPush(): WebPushState {
  const [supported] = useState(
    () =>
      typeof window !== 'undefined' &&
      'serviceWorker' in navigator &&
      'PushManager' in window &&
      'Notification' in window,
  );
  const [permission, setPermission] = useState<NotificationPermission | 'unsupported'>(
    supported ? Notification.permission : 'unsupported',
  );
  const [subscribed, setSubscribed] = useState(false);
  const [configured, setConfigured] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!supported) return;
    setPermission(Notification.permission);
    try {
      const vapid = await api.getVapidPublicKey();
      setConfigured(vapid.configured && Boolean(vapid.public_key));
      const reg = await navigator.serviceWorker.getRegistration('/');
      const sub = await reg?.pushManager.getSubscription();
      setSubscribed(Boolean(sub));
    } catch {
      setConfigured(false);
      setSubscribed(false);
    }
  }, [supported]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function enable() {
    if (!supported) return;
    setBusy(true);
    setError(null);
    try {
      const vapid = await api.getVapidPublicKey();
      if (!vapid.configured || !vapid.public_key) {
        throw new Error('Web push is not configured on the server (missing VAPID keys).');
      }
      const perm = await Notification.requestPermission();
      setPermission(perm);
      if (perm !== 'granted') {
        throw new Error('Notification permission was not granted.');
      }
      const reg =
        (await navigator.serviceWorker.getRegistration('/')) ??
        (await navigator.serviceWorker.register('/sw.js', { scope: '/' }));
      await navigator.serviceWorker.ready;
      let sub = await reg.pushManager.getSubscription();
      if (!sub) {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(vapid.public_key) as BufferSource,
        });
      }
      const json = sub.toJSON();
      await api.subscribeWebPush({
        endpoint: json.endpoint!,
        keys: {
          p256dh: json.keys?.p256dh || '',
          auth: json.keys?.auth || '',
        },
        user_agent: navigator.userAgent,
      });
      setSubscribed(true);
      setConfigured(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not enable push notifications.');
      setSubscribed(false);
    } finally {
      setBusy(false);
    }
  }

  async function disable() {
    if (!supported) return;
    setBusy(true);
    setError(null);
    try {
      const reg = await navigator.serviceWorker.getRegistration('/');
      const sub = await reg?.pushManager.getSubscription();
      if (sub) {
        await api.unsubscribeWebPush(sub.endpoint);
        await sub.unsubscribe();
      }
      setSubscribed(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not disable push notifications.');
    } finally {
      setBusy(false);
    }
  }

  return {
    supported,
    permission,
    subscribed,
    configured,
    busy,
    error,
    enable,
    disable,
  };
}
