import { Platform } from 'react-native';
import Constants from 'expo-constants';
import * as Notifications from 'expo-notifications';
import { api } from '../api';

const TOKEN_KEY_HINT = 'cp_mobile_push_token';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

let cachedToken: string | null = null;

export function getCachedPushToken(): string | null {
  return cachedToken;
}

/**
 * Request permission and register a native FCM/APNs device token with the API.
 * Expo Go usually cannot produce a device token usable by Firebase Admin —
 * use an EAS development/preview build for real push delivery.
 */
export async function registerForPushAlerts(): Promise<{
  token: string | null;
  status: 'registered' | 'denied' | 'unavailable' | 'error';
  detail?: string;
}> {
  try {
    if (Platform.OS === 'web') {
      return { token: null, status: 'unavailable', detail: 'Web uses VAPID, not mobile push.' };
    }

    const { status: existing } = await Notifications.getPermissionsAsync();
    let finalStatus = existing;
    if (existing !== 'granted') {
      const req = await Notifications.requestPermissionsAsync();
      finalStatus = req.status;
    }
    if (finalStatus !== 'granted') {
      return { token: null, status: 'denied', detail: 'Notification permission not granted.' };
    }

    // Prefer native device tokens for backend firebase_admin sender.
    let token: string;
    try {
      const device = await Notifications.getDevicePushTokenAsync();
      token = typeof device.data === 'string' ? device.data : String(device.data);
    } catch (err) {
      return {
        token: null,
        status: 'unavailable',
        detail:
          err instanceof Error
            ? `${err.message} — use an EAS dev/preview build (not Expo Go) for FCM/APNs tokens.`
            : 'Device push token unavailable in this client.',
      };
    }

    if (!token || token.startsWith('ExponentPushToken')) {
      return {
        token: null,
        status: 'unavailable',
        detail: 'Expo push tokens are not accepted by the FCM backend. Build with EAS.',
      };
    }

    const deviceId =
      (Constants as { sessionId?: string }).sessionId ??
      `${Platform.OS}-${Constants.expoConfig?.slug ?? 'care-plus'}`;

    await api.registerMobilePushDevice({
      token,
      platform: Platform.OS === 'ios' ? 'apns' : 'fcm',
      device_id: deviceId,
      app_version: Constants.expoConfig?.version,
    });
    cachedToken = token;
    return { token, status: 'registered' };
  } catch (err) {
    return {
      token: null,
      status: 'error',
      detail: err instanceof Error ? err.message : 'Push registration failed',
    };
  }
}

export async function unregisterPushAlerts(): Promise<void> {
  const token = cachedToken;
  cachedToken = null;
  if (!token) return;
  try {
    await api.unregisterMobilePushDevice(token);
  } catch {
    // best-effort on logout
  }
}

/** @internal reserved for SecureStore persistence later */
export const _tokenStorageKey = TOKEN_KEY_HINT;
