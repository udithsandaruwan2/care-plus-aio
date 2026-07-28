export type BookingIntent = {
  caregiverId: number;
  caregiverName: string;
  createdAt: number;
};

const KEY = 'cp.booking.intent';

export function saveBookingIntent(intent: BookingIntent) {
  window.localStorage.setItem(KEY, JSON.stringify(intent));
}

export function readBookingIntent(): BookingIntent | null {
  const raw = window.localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as BookingIntent;
    if (!parsed?.caregiverId || !parsed?.caregiverName) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function clearBookingIntent() {
  window.localStorage.removeItem(KEY);
}

