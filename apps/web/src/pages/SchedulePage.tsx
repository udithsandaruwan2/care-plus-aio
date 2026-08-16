import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  ApiError,
  ShiftConflictBody,
  type CaregiverAvailabilitySlot,
  type CaregiverProfile,
  type Shift,
  type ShiftConflictFallback,
} from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { PageHeader } from '../components/ui/PageHeader';
import {
  COLOMBO_TZ,
  formatColomboDateTime,
  formatColomboTime,
  nextSlotOccurrences,
  weekdayLabel,
} from '../lib/colomboSchedule';

const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6] as const;

function parseConflictFallback(err: unknown): ShiftConflictFallback | null {
  if (!(err instanceof ApiError) || err.status !== 409 || !err.body) return null;
  const parsed = ShiftConflictBody.safeParse(err.body);
  if (!parsed.success || !parsed.data.fallback) return null;
  return parsed.data.fallback;
}

export function SchedulePage() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const preselectCg = Number(params.get('caregiver') || '') || null;

  const isPatient = user?.role === 'patient';
  const isCaregiver = user?.role === 'caregiver';

  const [shifts, setShifts] = useState<Shift[]>([]);
  const [slots, setSlots] = useState<CaregiverAvailabilitySlot[]>([]);
  const [caregivers, setCaregivers] = useState<CaregiverProfile[]>([]);
  const [selectedCg, setSelectedCg] = useState<number | null>(preselectCg);
  const [publicSlots, setPublicSlots] = useState<CaregiverAvailabilitySlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState('');
  const [fallback, setFallback] = useState<ShiftConflictFallback | null>(null);
  const [picked, setPicked] = useState<{
    slotId: number;
    starts_at: string;
    ends_at: string;
    label: string;
  } | null>(null);

  // Caregiver weekly slot form
  const [weekday, setWeekday] = useState(0);
  const [startTime, setStartTime] = useState('09:00');
  const [endTime, setEndTime] = useState('12:00');

  const loadShifts = useCallback(() => {
    return api
      .listShifts()
      .then(setShifts)
      .catch((err) => {
        setShifts([]);
        setError(err instanceof Error ? err.message : 'Could not load shifts.');
      });
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const tasks: Promise<unknown>[] = [loadShifts()];

    if (isCaregiver) {
      tasks.push(
        api
          .listMyAvailabilitySlots()
          .then((rows) => {
            if (!cancelled) setSlots(rows);
          })
          .catch(() => {
            if (!cancelled) setSlots([]);
          }),
      );
    }

    if (isPatient) {
      tasks.push(
        api
          .caregivers({ available: 'true', page_size: 50 })
          .then((res) => {
            if (!cancelled) {
              setCaregivers(res.results);
              if (preselectCg && res.results.some((c) => c.id === preselectCg)) {
                setSelectedCg(preselectCg);
              } else if (!preselectCg && res.results[0]) {
                setSelectedCg(res.results[0].id);
              }
            }
          })
          .catch(() => {
            if (!cancelled) setCaregivers([]);
          }),
      );
    }

    Promise.all(tasks).finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [isCaregiver, isPatient, loadShifts, preselectCg]);

  useEffect(() => {
    if (!isPatient || !selectedCg) {
      setPublicSlots([]);
      return;
    }
    let cancelled = false;
    api
      .listCaregiverAvailabilitySlots(selectedCg)
      .then((rows) => {
        if (!cancelled) setPublicSlots(rows.filter((s) => s.is_active !== false));
      })
      .catch(() => {
        if (!cancelled) setPublicSlots([]);
      });
    return () => {
      cancelled = true;
    };
  }, [isPatient, selectedCg]);

  const occurrences = useMemo(() => {
    const list: Array<{
      slotId: number;
      starts_at: string;
      ends_at: string;
      label: string;
      weekday: number;
    }> = [];
    for (const slot of publicSlots) {
      for (const occ of nextSlotOccurrences(slot.weekday, slot.start_time, slot.end_time, 2)) {
        list.push({
          slotId: slot.id,
          starts_at: occ.starts_at,
          ends_at: occ.ends_at,
          label: occ.label,
          weekday: slot.weekday,
        });
      }
    }
    return list.sort((a, b) => a.starts_at.localeCompare(b.starts_at)).slice(0, 12);
  }, [publicSlots]);

  const booked = shifts.filter((s) => s.status === 'booked');
  const cancelled = shifts.filter((s) => s.status === 'cancelled');

  async function onBook(e: FormEvent) {
    e.preventDefault();
    if (!picked || !selectedCg || busy) return;
    setBusy(true);
    setError(null);
    setFallback(null);
    try {
      await api.createShift({
        caregiver_id: selectedCg,
        starts_at: picked.starts_at,
        ends_at: picked.ends_at,
        availability_slot_id: picked.slotId,
        notes: notes.trim() || undefined,
        timezone: COLOMBO_TZ,
      });
      setNotes('');
      setPicked(null);
      await loadShifts();
    } catch (err) {
      const offer = parseConflictFallback(err);
      if (offer) {
        setFallback(offer);
        setError('That window was just taken. VEHMF found another caregiver for the same time.');
      } else if (err instanceof ApiError && err.status === 409) {
        setError('That time window overlaps an existing booking.');
      } else {
        setError(err instanceof Error ? err.message : 'Could not book shift.');
      }
    } finally {
      setBusy(false);
    }
  }

  async function onAcceptFallback() {
    if (!fallback || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.createShift({
        caregiver_id: fallback.caregiver_id,
        starts_at: fallback.starts_at,
        ends_at: fallback.ends_at,
        availability_slot_id: fallback.availability_slot_id,
        notes: notes.trim() || undefined,
        timezone: COLOMBO_TZ,
      });
      setNotes('');
      setPicked(null);
      setFallback(null);
      setSelectedCg(fallback.caregiver_id);
      await loadShifts();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not book fallback caregiver.');
    } finally {
      setBusy(false);
    }
  }

  async function onCancelShift(id: number) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.cancelShift(id);
      await loadShifts();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not cancel shift.');
    } finally {
      setBusy(false);
    }
  }

  async function onAddSlot(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.createMyAvailabilitySlot({
        weekday,
        start_time: normalizeTime(startTime),
        end_time: normalizeTime(endTime),
        timezone: COLOMBO_TZ,
        is_active: true,
      });
      const rows = await api.listMyAvailabilitySlots();
      setSlots(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not publish slot.');
    } finally {
      setBusy(false);
    }
  }

  async function onDeleteSlot(id: number) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteMyAvailabilitySlot(id);
      setSlots((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not remove slot.');
    } finally {
      setBusy(false);
    }
  }

  if (!isPatient && !isCaregiver) {
    return (
      <div className="mx-auto max-w-3xl">
        <PageHeader title="Schedule" subtitle="Only patients and caregivers use the calendar." />
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col">
      <PageHeader
        eyebrow="Calendar"
        title="Care schedule"
        subtitle={`Book and manage shifts in ${COLOMBO_TZ}. All times shown in Sri Lanka local time.`}
      />

      {loading && <p className="mt-8 text-sm text-muted">Loading schedule…</p>}
      {error && (
        <p className="mt-6 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
          {error}
        </p>
      )}

      {fallback && (
        <div className="mt-4 rounded-2xl border border-cyan/40 bg-cyan/5 p-4">
          <p className="font-display text-mist">{fallback.display_name}</p>
          <p className="mt-1 text-sm text-muted">{fallback.explanation}</p>
          <p className="mt-1 text-xs text-muted">
            {formatColomboDateTime(fallback.starts_at)} – {formatColomboTime(fallback.ends_at)}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button disabled={busy} onClick={() => void onAcceptFallback()}>
              {busy ? 'Booking…' : 'Book this caregiver'}
            </Button>
            <Button tone="ghost" disabled={busy} onClick={() => setFallback(null)}>
              Dismiss
            </Button>
            <Link
              to={`/caregivers/${fallback.caregiver_id}`}
              className="text-sm text-cyan hover:underline self-center"
            >
              View profile
            </Link>
          </div>
        </div>
      )}

      <section className="mt-8">
        <h2 className="font-display text-lg text-mist">
          {isPatient ? 'Your bookings' : 'Booked with you'}
        </h2>
        {booked.length === 0 && (
          <p className="mt-3 text-sm text-muted">
            No upcoming shifts in Sri Lanka time (Asia/Colombo).
            {isPatient && (
              <>
                {' '}
                Pick a caregiver below or{' '}
                <Link to="/caregivers" className="text-cyan hover:underline">
                  browse profiles
                </Link>
                .
              </>
            )}
          </p>
        )}
        <ul className="mt-4 space-y-3">
          {booked.map((shift) => (
            <li
              key={shift.id}
              className="flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-hair bg-panel/60 p-4"
            >
              <div>
                <p className="font-display text-mist">
                  {isPatient ? shift.caregiver_name : shift.patient_email}
                </p>
                <p className="mt-1 text-sm text-muted">
                  {formatColomboDateTime(shift.starts_at)} – {formatColomboTime(shift.ends_at)}
                </p>
                {shift.notes && <p className="mt-1 text-xs text-muted">{shift.notes}</p>}
              </div>
              <Button
                tone="danger"
                className="min-h-9 px-3 py-1.5 text-xs"
                disabled={busy}
                onClick={() => void onCancelShift(shift.id)}
              >
                Cancel
              </Button>
            </li>
          ))}
        </ul>
        {cancelled.length > 0 && (
          <p className="mt-4 text-xs text-muted">
            {cancelled.length} cancelled shift(s) in history.
          </p>
        )}
      </section>

      {isPatient && (
        <section className="mt-10">
          <h2 className="font-display text-lg text-mist">Book a shift</h2>
          <p className="mt-1 text-sm text-muted">
            Choose a caregiver and an upcoming window from their weekly availability.
          </p>

          <label className="mt-4 block space-y-1.5">
            <span className="text-xs uppercase tracking-wide text-muted">Caregiver</span>
            <select
              className="min-h-11 w-full rounded-2xl border border-hair bg-elevated px-3.5 py-2.5 text-sm text-mist outline-none"
              value={selectedCg ?? ''}
              onChange={(e) => {
                setSelectedCg(Number(e.target.value) || null);
                setPicked(null);
              }}
            >
              {caregivers.map((cg) => (
                <option key={cg.id} value={cg.id}>
                  {cg.display_name}
                  {cg.city ? ` · ${cg.city}` : ''}
                </option>
              ))}
            </select>
          </label>

          {selectedCg && occurrences.length === 0 && (
            <p className="mt-4 text-sm text-muted">
              This caregiver hasn’t published weekly slots yet. Try another profile or ask them to
              add availability.
            </p>
          )}

          {occurrences.length > 0 && (
            <ul className="mt-4 space-y-2">
              {occurrences.map((occ) => {
                const active = picked?.starts_at === occ.starts_at && picked?.slotId === occ.slotId;
                return (
                  <li key={`${occ.slotId}-${occ.starts_at}`}>
                    <button
                      type="button"
                      onClick={() =>
                        setPicked({
                          slotId: occ.slotId,
                          starts_at: occ.starts_at,
                          ends_at: occ.ends_at,
                          label: occ.label,
                        })
                      }
                      className={`w-full rounded-xl border px-4 py-3 text-left text-sm transition ${
                        active
                          ? 'border-cyan/60 bg-cyan/10 text-cyan'
                          : 'border-hair text-muted hover:border-cyan/40 hover:text-mist'
                      }`}
                    >
                      <span className="text-mist">{weekdayLabel(occ.weekday)}</span>
                      <span className="mt-0.5 block text-xs">{occ.label}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          {picked && (
            <form onSubmit={(e) => void onBook(e)} className="mt-4 space-y-3">
              <p className="text-sm text-mint">Selected: {picked.label}</p>
              <label className="block space-y-1.5">
                <span className="text-xs uppercase tracking-wide text-muted">Notes (optional)</span>
                <Input
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g. morning medication support"
                />
              </label>
              <Button type="submit" disabled={busy}>
                {busy ? 'Booking…' : 'Confirm booking'}
              </Button>
            </form>
          )}
        </section>
      )}

      {isCaregiver && (
        <section className="mt-10">
          <h2 className="font-display text-lg text-mist">Weekly availability</h2>
          <p className="mt-1 text-sm text-muted">
            Publish recurring windows patients can book ({COLOMBO_TZ}).
          </p>

          <ul className="mt-4 space-y-2">
            {slots.map((slot) => (
              <li
                key={slot.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-hair bg-panel shadow-[var(--cp-shadow-soft)] px-4 py-3 text-sm"
              >
                <span className="text-mist">
                  {slot.weekday_label ?? weekdayLabel(slot.weekday)} · {slot.start_time.slice(0, 5)}{' '}
                  – {slot.end_time.slice(0, 5)}
                </span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void onDeleteSlot(slot.id)}
                  className="text-xs text-rose hover:underline"
                >
                  Remove
                </button>
              </li>
            ))}
            {slots.length === 0 && (
              <p className="text-sm text-muted">
                No weekly windows yet. Add slots below so families in your city can book.
              </p>
            )}
          </ul>

          <form onSubmit={(e) => void onAddSlot(e)} className="mt-6 grid gap-3 sm:grid-cols-3">
            <label className="block space-y-1.5 sm:col-span-1">
              <span className="text-xs uppercase tracking-wide text-muted">Weekday</span>
              <select
                className="min-h-11 w-full rounded-2xl border border-hair bg-elevated px-3 py-2 text-sm text-mist"
                value={weekday}
                onChange={(e) => setWeekday(Number(e.target.value))}
              >
                {WEEKDAYS.map((d) => (
                  <option key={d} value={d}>
                    {weekdayLabel(d)}
                  </option>
                ))}
              </select>
            </label>
            <label className="block space-y-1.5">
              <span className="text-xs uppercase tracking-wide text-muted">Start</span>
              <Input
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                required
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-xs uppercase tracking-wide text-muted">End</span>
              <Input
                type="time"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                required
              />
            </label>
            <div className="sm:col-span-3">
              <Button type="submit" disabled={busy}>
                {busy ? 'Saving…' : 'Publish slot'}
              </Button>
            </div>
          </form>

          <p className="mt-4 text-xs text-muted">
            Match availability is still controlled on{' '}
            <Link to="/presence" className="text-cyan hover:underline">
              Availability
            </Link>
            .
          </p>
        </section>
      )}
    </div>
  );
}

function normalizeTime(value: string): string {
  const trimmed = value.trim();
  if (/^\d{2}:\d{2}$/.test(trimmed)) return `${trimmed}:00`;
  if (/^\d{2}:\d{2}:\d{2}/.test(trimmed)) return trimmed.slice(0, 8);
  return trimmed;
}
