import { useEffect, useId, useRef, useState } from 'react';
import { Calendar, Send, X } from 'lucide-react';
import type { CaregiverAvailabilitySlot, CaregiverDetail } from '@care-plus/api-client';
import { api } from '../auth/api';
import { Avatar } from '../components/ui/Avatar';
import { nextSlotOccurrences, type SlotOccurrence } from '../lib/colomboSchedule';
import { caregiverSpokenSummary } from './caregiverSpokenSummary';
import { executeSerahAction } from './executeSerahAction';
import { useAssistant } from './store';
import {
  isSerahSpeaking,
  speakSerah,
  subscribeSerahSpeaking,
} from './useTts';

function waitForSerahIdle(): Promise<void> {
  if (!isSerahSpeaking()) return Promise.resolve();
  return new Promise((resolve) => {
    const unsub = subscribeSerahSpeaking((active) => {
      if (!active) {
        unsub();
        resolve();
      }
    });
  });
}

type Pane = 'profile' | 'compose' | 'schedule';

function paneFromStage(stage: string): Pane {
  if (stage === 'compose' || stage === 'requested' || stage === 'awaiting_accept') return 'compose';
  if (stage === 'schedule') return 'schedule';
  return 'profile';
}

/**
 * Right-side caregiver card on the Serah screen.
 * Profile, typed request note, and schedule stay here — no navigation away.
 */
export function CaregiverProfileDrawer() {
  const titleId = useId();
  const focusedCaregiverId = useAssistant((s) => s.focusedCaregiverId);
  const bookingStage = useAssistant((s) => s.bookingStage);
  const profileNarrateMode = useAssistant((s) => s.profileNarrateMode);
  const uiLanguage = useAssistant((s) => s.uiLanguage);
  const composeDraft = useAssistant((s) => s.composeDraft);
  const setFocusedCaregiverId = useAssistant((s) => s.setFocusedCaregiverId);
  const setBookingStage = useAssistant((s) => s.setBookingStage);
  const clearProfileNarrate = useAssistant((s) => s.clearProfileNarrate);
  const resetComposeDraft = useAssistant((s) => s.resetComposeDraft);
  const matchHit = useAssistant((s) =>
    focusedCaregiverId
      ? s.match?.results?.find((h) => h.caregiver_id === focusedCaregiverId)
      : undefined,
  );

  const open = focusedCaregiverId != null && focusedCaregiverId > 0;
  const [pane, setPane] = useState<Pane>('profile');
  const [profile, setProfile] = useState<CaregiverDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visibleNote, setVisibleNote] = useState('');
  const [sending, setSending] = useState(false);
  const [slots, setSlots] = useState<CaregiverAvailabilitySlot[]>([]);
  const [slotError, setSlotError] = useState<string | null>(null);
  const [booking, setBooking] = useState(false);
  const [bookedLabel, setBookedLabel] = useState<string | null>(null);
  const spokenKeyRef = useRef<string | null>(null);
  const fetchGenRef = useRef(0);
  const submitLockRef = useRef(false);

  useEffect(() => {
    if (!open) return;
    setPane(paneFromStage(bookingStage));
  }, [open, bookingStage]);

  useEffect(() => {
    if (!open || focusedCaregiverId == null) {
      setProfile(null);
      setError(null);
      setLoading(false);
      setSlots([]);
      setBookedLabel(null);
      spokenKeyRef.current = null;
      return;
    }

    const gen = ++fetchGenRef.current;
    let cancelled = false;
    setLoading(true);
    setError(null);

    void api
      .caregiver(focusedCaregiverId)
      .then((detail) => {
        if (cancelled || gen !== fetchGenRef.current) return;
        setProfile(detail);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled || gen !== fetchGenRef.current) return;
        setProfile(null);
        setLoading(false);
        setError(err instanceof Error ? err.message : 'Could not load caregiver profile.');
      });

    return () => {
      cancelled = true;
    };
  }, [open, focusedCaregiverId]);

  useEffect(() => {
    if (!open || focusedCaregiverId == null || pane !== 'schedule') return;
    let cancelled = false;
    setSlotError(null);
    void api
      .listCaregiverAvailabilitySlots(focusedCaregiverId)
      .then((rows) => {
        if (!cancelled) setSlots(rows.filter((s) => s.is_active !== false));
      })
      .catch((err) => {
        if (!cancelled) {
          setSlots([]);
          setSlotError(err instanceof Error ? err.message : 'Could not load availability.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open, focusedCaregiverId, pane]);

  useEffect(() => {
    if (!open || pane !== 'compose' || !composeDraft.fullText) {
      setVisibleNote('');
      return;
    }
    const text = composeDraft.fullText;
    let i = 0;
    setVisibleNote('');
    submitLockRef.current = false;
    const id = window.setInterval(() => {
      i += 2;
      setVisibleNote(text.slice(0, i));
      if (i >= text.length) {
        window.clearInterval(id);
        if (composeDraft.autoSubmit && !submitLockRef.current) {
          submitLockRef.current = true;
          setSending(true);
          void executeSerahAction({ type: 'submit_request' }).finally(() => setSending(false));
        }
      }
    }, 18);
    return () => window.clearInterval(id);
  }, [open, pane, composeDraft.fullText, composeDraft.autoSubmit]);

  useEffect(() => {
    if (!open || !profile || !profileNarrateMode) return;
    const key = `${profile.id}:${profileNarrateMode}`;
    if (spokenKeyRef.current === key) return;
    spokenKeyRef.current = key;

    const mode = profileNarrateMode;
    const summary = caregiverSpokenSummary(profile, mode);
    const lang = uiLanguage;
    let cancelled = false;

    void (async () => {
      await waitForSerahIdle();
      if (cancelled) return;
      clearProfileNarrate();
      const store = useAssistant.getState();
      const last = [...store.chat].reverse().find((m) => m.role === 'serah');
      if (last?.text.trim() !== summary.trim()) {
        store.appendChat({ role: 'serah', text: summary, route: 'ACTION' });
      }
      await speakSerah(summary, lang);
    })();

    return () => {
      cancelled = true;
    };
  }, [open, profile, profileNarrateMode, uiLanguage, clearProfileNarrate]);

  function closeDrawer() {
    setFocusedCaregiverId(null);
    clearProfileNarrate();
    resetComposeDraft();
    if (
      bookingStage === 'profile' ||
      bookingStage === 'compose' ||
      bookingStage === 'schedule'
    ) {
      setBookingStage('idle');
    }
  }

  if (!open) return null;

  const name = profile?.display_name || matchHit?.display_name || 'Caregiver';
  const photoUrl = profile?.photo_url ?? matchHit?.photo_url ?? null;
  const occurrences = slots.flatMap((slot) =>
    nextSlotOccurrences(slot.weekday, slot.start_time, slot.end_time, 2).map((occ) => ({
      slot,
      occ,
    })),
  );

  async function bookOccurrence(occ: SlotOccurrence, slotId: number) {
    if (!focusedCaregiverId || booking) return;
    setBooking(true);
    setSlotError(null);
    try {
      await api.createShift({
        caregiver_id: focusedCaregiverId,
        starts_at: occ.starts_at,
        ends_at: occ.ends_at,
        availability_slot_id: slotId,
        notes: composeDraft.fullText || undefined,
        timezone: 'Asia/Colombo',
      });
      setBookedLabel(occ.label);
      const line = `Booked ${occ.label} with ${name}.`;
      const store = useAssistant.getState();
      store.appendChat({ role: 'serah', text: line, route: 'ACTION' });
      void speakSerah(line, uiLanguage);
    } catch (err) {
      setSlotError(err instanceof Error ? err.message : 'Could not book that time.');
    } finally {
      setBooking(false);
    }
  }

  return (
    <aside
      className="serah-profile-drawer is-open"
      role="dialog"
      aria-modal="false"
      aria-labelledby={titleId}
      data-testid="serah-profile-drawer"
    >
      <div className="serah-profile-drawer-head">
        <p className="serah-profile-drawer-eyebrow">
          {pane === 'compose'
            ? 'Care request'
            : pane === 'schedule'
              ? 'Schedule'
              : 'Caregiver profile'}
        </p>
        <button
          type="button"
          className="serah-profile-drawer-close"
          onClick={closeDrawer}
          aria-label="Close caregiver card"
        >
          <X size={18} />
        </button>
      </div>

      <div className="serah-profile-drawer-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={pane === 'profile'}
          className={pane === 'profile' ? 'is-active' : ''}
          onClick={() => {
            setPane('profile');
            setBookingStage('profile');
          }}
        >
          Profile
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={pane === 'compose'}
          className={pane === 'compose' ? 'is-active' : ''}
          onClick={() => {
            setPane('compose');
            void executeSerahAction({ type: 'request' });
          }}
        >
          Request
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={pane === 'schedule'}
          className={pane === 'schedule' ? 'is-active' : ''}
          onClick={() => {
            setPane('schedule');
            void executeSerahAction({ type: 'book_shift' });
          }}
        >
          Schedule
        </button>
      </div>

      {loading && !profile ? (
        <p className="serah-profile-drawer-status" role="status">
          Loading profile…
        </p>
      ) : null}
      {error && !profile ? (
        <p className="serah-profile-drawer-error" role="alert">
          {error}
        </p>
      ) : null}

      {(profile || matchHit) && pane === 'profile' ? (
        <div className="serah-profile-drawer-body serah-stage-enter">
          <div className="serah-profile-drawer-hero">
            <Avatar name={name} photoUrl={photoUrl} size="lg" className="rounded-2xl" />
            <div className="min-w-0">
              <h2 id={titleId} className="font-display text-lg text-mist">
                {name}
              </h2>
              <p className="mt-0.5 text-xs text-muted">
                {[
                  profile?.age ? `${profile.age} yrs` : matchHit?.age ? `${matchHit.age} yrs` : null,
                  profile?.approximate_area || profile?.city || null,
                  profile?.years_experience ? `${profile.years_experience} yrs exp` : null,
                ]
                  .filter(Boolean)
                  .join(' · ') || 'Sri Lanka'}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                {profile?.is_verified ? (
                  <span className="rounded-full border border-mint/40 px-2 py-0.5 text-[10px] uppercase tracking-wide text-mint">
                    Verified
                  </span>
                ) : null}
                <span
                  className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide ${
                    (profile?.is_available ?? matchHit?.is_available) === false
                      ? 'border-hair text-muted'
                      : 'border-cyan/40 text-cyan'
                  }`}
                >
                  {(profile?.is_available ?? matchHit?.is_available) === false
                    ? 'Unavailable'
                    : 'Available'}
                </span>
                {profile?.review_count ? (
                  <span className="text-[11px] text-amber">
                    ★ {(profile.review_average ?? 0).toFixed(1)} ({profile.review_count})
                  </span>
                ) : (
                  <span className="text-[11px] text-muted">No reviews yet</span>
                )}
              </div>
            </div>
          </div>

          {profile?.bio ? (
            <p className="serah-profile-drawer-bio">{profile.bio}</p>
          ) : matchHit?.explanation ? (
            <p className="serah-profile-drawer-bio">{matchHit.explanation}</p>
          ) : null}

          <dl className="serah-profile-drawer-meta">
            <div>
              <dt>Languages</dt>
              <dd>{(profile?.languages || matchHit?.languages || []).join(' · ') || '—'}</dd>
            </div>
            <div>
              <dt>Care levels</dt>
              <dd>{(profile?.care_levels || matchHit?.care_levels || []).join(' · ') || '—'}</dd>
            </div>
            <div>
              <dt>Specialties</dt>
              <dd>
                {(profile?.specialties || matchHit?.specialties || []).join(' · ') || 'General care'}
              </dd>
            </div>
            <div>
              <dt>Certifications</dt>
              <dd>{(profile?.certifications || []).join(' · ') || 'Not listed yet'}</dd>
            </div>
            {profile != null ? (
              <div>
                <dt>Trust</dt>
                <dd>{Math.round((profile.trust_score || 0) * 100)}</dd>
              </div>
            ) : null}
          </dl>

          <p className="serah-profile-drawer-hint">
            Stay here and keep talking — say “send the request” or “show the schedule”.
          </p>

          <div className="serah-profile-drawer-actions">
            <button
              type="button"
              className="serah-profile-drawer-cta"
              onClick={() => void executeSerahAction({ type: 'request' })}
            >
              <Send size={14} />
              Write & send request
            </button>
            <button
              type="button"
              className="serah-profile-drawer-full"
              onClick={() => void executeSerahAction({ type: 'book_shift' })}
            >
              <Calendar size={14} />
              Show schedule
            </button>
          </div>
        </div>
      ) : null}

      {pane === 'compose' ? (
        <div className="serah-profile-drawer-body serah-stage-enter" data-testid="serah-compose-pane">
          <p className="serah-profile-drawer-hint">
            Serah is writing a request to {name}. You can edit before it sends.
          </p>
          <textarea
            className="serah-compose-input"
            rows={7}
            value={visibleNote || composeDraft.fullText}
            onChange={(e) =>
              useAssistant.getState().setComposeDraft({
                fullText: e.target.value,
                autoSubmit: false,
              })
            }
            aria-label="Care request message"
          />
          <div className="serah-profile-drawer-actions">
            <button
              type="button"
              className="serah-profile-drawer-cta"
              disabled={sending || !(visibleNote || composeDraft.fullText).trim()}
              onClick={() => {
                submitLockRef.current = true;
                setSending(true);
                void executeSerahAction({ type: 'submit_request' }).finally(() => setSending(false));
              }}
            >
              <Send size={14} />
              {sending
                ? 'Sending…'
                : bookingStage === 'awaiting_accept' || bookingStage === 'requested'
                  ? 'Request sent'
                  : 'Send request'}
            </button>
            <button
              type="button"
              className="serah-profile-drawer-full"
              onClick={() => setPane('profile')}
            >
              Back to profile
            </button>
          </div>
        </div>
      ) : null}

      {pane === 'schedule' ? (
        <div className="serah-profile-drawer-body serah-stage-enter" data-testid="serah-schedule-pane">
          <p className="serah-profile-drawer-hint">
            Upcoming times for {name} (Asia/Colombo). Book one here — you stay with Serah.
          </p>
          {slotError ? (
            <p className="serah-profile-drawer-error" role="alert">
              {slotError}
            </p>
          ) : null}
          {bookedLabel ? (
            <p className="serah-profile-drawer-status" role="status">
              Booked {bookedLabel}
            </p>
          ) : null}
          {occurrences.length === 0 && !slotError ? (
            <p className="serah-profile-drawer-status">No published slots yet.</p>
          ) : (
            <ul className="serah-schedule-list">
              {occurrences.map(({ slot, occ }) => (
                <li key={`${slot.id}-${occ.starts_at}`}>
                  <button
                    type="button"
                    className="serah-schedule-slot"
                    disabled={booking}
                    onClick={() => void bookOccurrence(occ, slot.id)}
                  >
                    <span>{occ.label}</span>
                    <span>{booking ? 'Booking…' : 'Book'}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <button
            type="button"
            className="serah-profile-drawer-full"
            onClick={() => setPane('profile')}
          >
            Back to profile
          </button>
        </div>
      ) : null}
    </aside>
  );
}
