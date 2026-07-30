/** Asia/Colombo scheduling helpers (Step 52). */

export const COLOMBO_TZ = 'Asia/Colombo';

const WEEKDAY_LABELS = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
] as const;

export function weekdayLabel(weekday: number): string {
  return WEEKDAY_LABELS[weekday] ?? `Day ${weekday}`;
}

/** Format an ISO instant for display in Asia/Colombo. */
export function formatColomboDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat('en-LK', {
    timeZone: COLOMBO_TZ,
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(d);
}

export function formatColomboTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat('en-LK', {
    timeZone: COLOMBO_TZ,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(d);
}

function colomboParts(date: Date) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: COLOMBO_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(date);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
  return {
    year: Number(get('year')),
    month: Number(get('month')),
    day: Number(get('day')),
    hour: Number(get('hour')),
    minute: Number(get('minute')),
    second: Number(get('second')),
    weekdayShort: get('weekday'),
  };
}

/** JS Date.getUTCDay()-style weekday in Colombo: 0=Mon … 6=Sun (matches backend). */
export function colomboWeekday(date: Date): number {
  const map: Record<string, number> = {
    Mon: 0,
    Tue: 1,
    Wed: 2,
    Thu: 3,
    Fri: 4,
    Sat: 5,
    Sun: 6,
  };
  return map[colomboParts(date).weekdayShort] ?? 0;
}

/**
 * Build an ISO string for a Colombo local wall time on a given Y-M-D.
 * Uses a fixed +05:30 offset (Sri Lanka has no DST).
 */
export function colomboLocalToIso(
  year: number,
  month: number,
  day: number,
  hour: number,
  minute: number,
  second = 0,
): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${year}-${pad(month)}-${pad(day)}T${pad(hour)}:${pad(minute)}:${pad(second)}+05:30`;
}

function parseHm(value: string): { hour: number; minute: number } {
  const [h, m] = value.slice(0, 5).split(':').map(Number);
  return { hour: h || 0, minute: m || 0 };
}

export type SlotOccurrence = {
  starts_at: string;
  ends_at: string;
  label: string;
};

/**
 * Next `count` dated occurrences of a weekly slot in Asia/Colombo,
 * starting from "now" (skips past windows on today).
 */
export function nextSlotOccurrences(
  weekday: number,
  startTime: string,
  endTime: string,
  count = 4,
  from: Date = new Date(),
): SlotOccurrence[] {
  const startHm = parseHm(startTime);
  const endHm = parseHm(endTime);
  const out: SlotOccurrence[] = [];
  const cursor = new Date(from.getTime());

  for (let guard = 0; guard < 60 && out.length < count; guard += 1) {
    const parts = colomboParts(cursor);
    const wd = colomboWeekday(cursor);
    if (wd === weekday) {
      const startsIso = colomboLocalToIso(
        parts.year,
        parts.month,
        parts.day,
        startHm.hour,
        startHm.minute,
      );
      const endsIso = colomboLocalToIso(
        parts.year,
        parts.month,
        parts.day,
        endHm.hour,
        endHm.minute,
      );
      if (new Date(endsIso).getTime() > from.getTime()) {
        out.push({
          starts_at: startsIso,
          ends_at: endsIso,
          label: `${formatColomboDateTime(startsIso)} – ${formatColomboTime(endsIso)}`,
        });
      }
    }
    // Advance one Colombo calendar day
    const next = new Date(cursor.getTime() + 24 * 60 * 60 * 1000);
    cursor.setTime(next.getTime());
  }
  return out;
}
