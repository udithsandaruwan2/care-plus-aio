import { useEffect, useId, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { X } from 'lucide-react';
import type { CaregiverDetail } from '@care-plus/api-client';
import { api } from '../auth/api';
import { Avatar } from '../components/ui/Avatar';
import { caregiverSpokenSummary } from './caregiverSpokenSummary';
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

/**
 * Right-side caregiver detail drawer on the Serah screen.
 * Opens from voice ``view_profile`` / ``describe_caregiver`` (store focus);
 * keeps mic + conversation alive — no navigation away.
 */
export function CaregiverProfileDrawer() {
  const titleId = useId();
  const focusedCaregiverId = useAssistant((s) => s.focusedCaregiverId);
  const bookingStage = useAssistant((s) => s.bookingStage);
  const profileNarrateMode = useAssistant((s) => s.profileNarrateMode);
  const uiLanguage = useAssistant((s) => s.uiLanguage);
  const setFocusedCaregiverId = useAssistant((s) => s.setFocusedCaregiverId);
  const setBookingStage = useAssistant((s) => s.setBookingStage);
  const clearProfileNarrate = useAssistant((s) => s.clearProfileNarrate);
  const matchHit = useAssistant((s) =>
    focusedCaregiverId
      ? s.match?.results?.find((h) => h.caregiver_id === focusedCaregiverId)
      : undefined,
  );

  const open = focusedCaregiverId != null && focusedCaregiverId > 0;
  const [profile, setProfile] = useState<CaregiverDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const spokenKeyRef = useRef<string | null>(null);
  const fetchGenRef = useRef(0);

  useEffect(() => {
    if (!open || focusedCaregiverId == null) {
      setProfile(null);
      setError(null);
      setLoading(false);
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
    if (bookingStage === 'profile') {
      setBookingStage('idle');
    }
  }

  if (!open) return null;

  const name = profile?.display_name || matchHit?.display_name || 'Caregiver';
  const photoUrl = profile?.photo_url ?? matchHit?.photo_url ?? null;

  return (
    <aside
      className="serah-profile-drawer is-open"
      role="dialog"
      aria-modal="false"
      aria-labelledby={titleId}
      data-testid="serah-profile-drawer"
    >
      <div className="serah-profile-drawer-head">
        <p className="serah-profile-drawer-eyebrow">Caregiver profile</p>
        <button
          type="button"
          className="serah-profile-drawer-close"
          onClick={closeDrawer}
          aria-label="Close caregiver profile"
        >
          <X size={18} />
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

      {(profile || matchHit) && (
        <div className="serah-profile-drawer-body">
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
                  profile?.years_experience
                    ? `${profile.years_experience} yrs exp`
                    : null,
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
              <dd>
                {(profile?.languages || matchHit?.languages || []).join(' · ') || '—'}
              </dd>
            </div>
            <div>
              <dt>Care levels</dt>
              <dd>
                {(profile?.care_levels || matchHit?.care_levels || []).join(' · ') || '—'}
              </dd>
            </div>
            <div>
              <dt>Specialties</dt>
              <dd>
                {(profile?.specialties || matchHit?.specialties || []).join(' · ') ||
                  'General care'}
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
            Stay on this screen and keep talking — say “send the request” when ready.
          </p>

          <Link
            to={`/caregivers/${focusedCaregiverId}`}
            className="serah-profile-drawer-full"
          >
            Open full profile page
          </Link>
        </div>
      )}
    </aside>
  );
}
