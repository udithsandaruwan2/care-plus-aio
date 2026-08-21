import { FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import type { CaregiverDetail } from '@care-plus/api-client';
import { ApiError } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { clearBookingIntent, readBookingIntent, saveBookingIntent } from '../booking/intent';
import { PublicPage } from '../components/layout/PublicPage';
import { Avatar } from '../components/ui/Avatar';
import { BackLink } from '../components/ui/BackLink';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { CacheSourceBadge } from '../lib/query/CacheSourceBadge';
import { queryKeys, STALE_MS } from '../lib/query/keys';
import { useCachedQuery } from '../lib/query/useCachedQuery';

function formatReviewDate(value?: string) {
  if (!value) return '';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString();
}

export function CaregiverDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const pk = Number(id);
  const validId = Number.isFinite(pk) && pk > 0;

  const query = useCachedQuery<CaregiverDetail>({
    key: validId ? queryKeys.caregiverDetail(pk) : null,
    staleTimeMs: STALE_MS.caregiverDetail,
    enabled: validId,
    fetcher: () => api.caregiver(pk),
  });

  const profile = query.data;
  const loading = query.loading && !query.data;
  const error = !validId
    ? 'Invalid caregiver link.'
    : query.error;

  const [requesting, setRequesting] = useState(false);
  const [requestSent, setRequestSent] = useState(false);
  const [resumeHint, setResumeHint] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [message, setMessage] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    const intent = readBookingIntent();
    if (!intent || !id) return;
    if (String(intent.caregiverId) === String(id) && user?.role === 'patient') {
      setResumeHint(true);
      setShowForm(true);
    }
  }, [id, user?.role]);

  function startBooking() {
    if (!profile || requesting || requestSent) return;
    if (!user) {
      saveBookingIntent({
        caregiverId: profile.id,
        caregiverName: profile.display_name,
        createdAt: Date.now(),
      });
      navigate('/login', { state: { from: `/caregivers/${profile.id}` } });
      return;
    }
    if (user.role !== 'patient') {
      setFormError('Only patient accounts can place care requests.');
      return;
    }
    setFormError(null);
    setShowForm(true);
  }

  async function onSubmitRequest(e: FormEvent) {
    e.preventDefault();
    if (!profile || requesting || requestSent) return;
    if (user?.role !== 'patient') {
      setFormError('Only patient accounts can place care requests.');
      return;
    }
    setRequesting(true);
    setFormError(null);
    try {
      const { enqueueCareRequest } = await import('../lib/outbox/flush');
      const outcome = await enqueueCareRequest({
        caregiver_id: profile.id,
        message: message.trim() || undefined,
      }, `Request to ${profile.display_name}`);
      setRequestSent(true);
      clearBookingIntent();
      if (outcome.queued) {
        setFormError(null);
        navigate('/requests');
      } else {
        navigate('/requests');
      }
    } catch (err) {
      const msg =
        err instanceof ApiError && typeof err.body === 'object' && err.body
          ? String((err.body as Record<string, unknown>).detail || 'Request failed.')
          : err instanceof Error
            ? err.message
            : 'Request failed.';
      setFormError(msg);
    } finally {
      setRequesting(false);
    }
  }

  return (
    <PublicPage>
      <BackLink to="/caregivers">Caregivers</BackLink>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="font-display text-sm uppercase tracking-[0.2em] text-cyan">
          Caregiver profile
        </p>
        <CacheSourceBadge fromCache={query.fromCache} stale={query.stale} />
      </div>

      {loading && <p className="mt-10 text-sm text-muted">Loading profile…</p>}
      {error && (
        <p className="mt-10 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
          {error}
        </p>
      )}

      {profile && !loading && (
        <section className="mt-8 space-y-10">
          {resumeHint && (
            <p className="rounded-2xl border border-mint/40 bg-mint/10 px-4 py-3 text-sm text-mint">
              Welcome back — finish your booking below when ready.
            </p>
          )}

          <div className="rounded-[1.5rem] border border-hair bg-panel p-6 shadow-[var(--cp-shadow-soft)]">
            <div className="flex flex-wrap items-start justify-between gap-6">
              <div className="flex min-w-0 flex-1 items-start gap-5">
                <Avatar
                  name={profile.display_name}
                  photoUrl={profile.photo_url}
                  size="xl"
                  className="rounded-[1.25rem]"
                />
                <div className="min-w-0">
                  <h1 className="font-display text-2xl text-mist">{profile.display_name}</h1>
                  <p className="mt-1 text-sm text-muted">
                    {[
                      profile.age ? `${profile.age} years old` : null,
                      profile.approximate_area || profile.city || 'Sri Lanka',
                      profile.years_experience
                        ? `${profile.years_experience} yrs experience`
                        : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    {profile.is_verified && (
                      <span className="rounded-full border border-mint/40 px-2.5 py-0.5 text-[11px] uppercase tracking-wide text-mint">
                        Verified
                      </span>
                    )}
                    <span
                      className={`rounded-full border px-2.5 py-0.5 text-[11px] uppercase tracking-wide ${
                        profile.is_available === false
                          ? 'border-hair text-muted'
                          : 'border-cyan/40 text-cyan'
                      }`}
                    >
                      {profile.is_available === false ? 'Unavailable' : 'Available now'}
                    </span>
                    <span className="text-[11px] text-amber">
                      {profile.review_count
                        ? `${'★'.repeat(
                            Math.max(1, Math.min(5, Math.round(profile.review_average ?? 0))),
                          )} ${(profile.review_average ?? 0).toFixed(1)} (${profile.review_count})`
                        : 'No reviews yet'}
                    </span>
                  </div>
                  <p className="mt-4 max-w-2xl text-sm leading-relaxed text-mist/90">
                    {profile.bio || 'Community caregiver on Care Plus.'}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-3xl text-mint">
                  {Math.round((profile.trust_score || 0) * 100)}
                </p>
                <p className="text-[11px] uppercase tracking-wide text-muted">trust</p>
              </div>
            </div>
          </div>

          <dl className="grid gap-6 sm:grid-cols-2">
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-muted">Languages</dt>
              <dd className="mt-1 text-sm text-cyan">
                {(profile.languages || []).join(' · ') || '—'}
              </dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-muted">Care levels</dt>
              <dd className="mt-1 text-sm text-mint">
                {(profile.care_levels || []).join(' · ') || '—'}
              </dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-muted">Specialties</dt>
              <dd className="mt-1 text-sm text-violet">
                {(profile.specialties || []).join(' · ') || 'General care'}
              </dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-muted">Certifications</dt>
              <dd className="mt-1 text-sm text-amber">
                {(profile.certifications || []).join(' · ') || 'Not listed yet'}
              </dd>
            </div>
          </dl>

          {!showForm && (
            <div className="rounded-[1.5rem] border border-cyan/30 bg-cyan/5 p-6">
              <h2 className="font-display text-lg text-mist">Book {profile.display_name}</h2>
              <ol className="mt-3 grid gap-2 text-sm text-muted sm:grid-cols-2 lg:grid-cols-4">
                {[
                  'Send a care request',
                  'Caregiver accepts',
                  'Choose a care package',
                  'Pay and care begins',
                ].map((step, i) => (
                  <li key={step} className="flex items-start gap-2">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-cyan/40 text-[11px] text-cyan">
                      {i + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
              <div className="mt-5 flex flex-wrap gap-2">
                <Button
                  type="button"
                  onClick={startBooking}
                  disabled={profile.is_available === false || requesting || requestSent}
                >
                  {requestSent
                    ? 'Request sent'
                    : user
                      ? 'Request this caregiver'
                      : 'Sign in to start booking'}
                </Button>
                {profile.is_available === false && (
                  <p className="self-center text-xs text-muted">
                    This caregiver is not accepting new families right now.
                  </p>
                )}
              </div>
            </div>
          )}

          {showForm && user?.role === 'patient' && !requestSent && (
            <form
              onSubmit={(e) => void onSubmitRequest(e)}
              className="max-w-lg space-y-4 rounded-[1.5rem] border border-hair bg-panel/70 p-5"
            >
              <p className="font-display text-lg text-mist">Send care request</p>
              <label className="block space-y-1.5">
                <span className="text-xs uppercase tracking-wide text-muted">
                  Message (optional)
                </span>
                <Input
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Share care needs, preferred start date, or location…"
                />
              </label>
              {formError && <p className="text-sm text-rose">{formError}</p>}
              <div className="flex flex-wrap gap-2">
                <Button type="submit" disabled={requesting}>
                  {requesting ? 'Sending…' : 'Submit request'}
                </Button>
                <Button type="button" tone="ghost" onClick={() => setShowForm(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          )}

          {formError && !showForm && <p className="text-sm text-rose">{formError}</p>}

          {user && (
            <p className="text-xs text-muted">
              <Link to="/requests" className="text-cyan hover:underline">
                View your care requests
              </Link>
            </p>
          )}

          <div>
            <h2 className="font-display text-lg text-mist">Reviews</h2>
            {profile.review_count > 0 && profile.reviews_teaser?.length ? (
              <>
                <p className="mt-2 text-sm text-mint">
                  {profile.review_average?.toFixed(1) ?? '—'} / 5 · {profile.review_count} review
                  {profile.review_count === 1 ? '' : 's'}
                </p>
                <ul className="mt-4 space-y-4">
                  {profile.reviews_teaser.map((r, i) => (
                    <li key={r.id ?? i} className="border-b border-hair/60 pb-4 last:border-0">
                      <p className="text-xs text-amber">
                        {'★'.repeat(Math.max(1, Math.min(5, Math.round(r.rating || 0))))}
                      </p>
                      <p className="mt-1 text-sm text-muted">{r.comment || 'Rated caregiver.'}</p>
                      {r.created_at && (
                        <p className="mt-1 text-[11px] text-muted">
                          Reviewed {formatReviewDate(r.created_at)}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="mt-2 text-sm text-muted">
                No family reviews yet — be among the first to share feedback after care.
              </p>
            )}
          </div>

          <div>
            <h2 className="font-display text-lg text-mist">Weekly availability</h2>
            <AvailabilitySlots caregiverId={profile.id} caregiverName={profile.display_name} />
            {user?.role === 'patient' && (
              <Link to={`/schedule?caregiver=${profile.id}`} className="mt-3 inline-block">
                <Button tone="ghost" className="min-h-9 px-3 py-1.5 text-xs">
                  Book a shift
                </Button>
              </Link>
            )}
            {!user && (
              <Link
                to="/login"
                state={{ from: `/schedule?caregiver=${profile.id}` }}
                className="mt-3 inline-block"
              >
                <Button tone="ghost" className="min-h-9 px-3 py-1.5 text-xs">
                  Sign in to book a shift
                </Button>
              </Link>
            )}
          </div>
        </section>
      )}
    </PublicPage>
  );
}

function AvailabilitySlots({ caregiverId }: { caregiverId: number; caregiverName?: string }) {
  const [slots, setSlots] = useState<
    Array<{
      id: number;
      weekday_label?: string;
      start_time: string;
      end_time: string;
      timezone: string;
    }>
  >([]);
  useEffect(() => {
    let cancelled = false;
    api
      .listCaregiverAvailabilitySlots(caregiverId)
      .then((rows) => {
        if (!cancelled) setSlots(rows);
      })
      .catch(() => {
        if (!cancelled) setSlots([]);
      });
    return () => {
      cancelled = true;
    };
  }, [caregiverId]);

  if (!slots.length)
    return (
      <p className="mt-2 text-sm text-muted">
        No weekly availability published yet (shown in Asia/Colombo).
      </p>
    );

  return (
    <ul className="mt-3 space-y-2 text-sm text-muted">
      {slots.map((s) => (
        <li key={s.id} className="rounded-xl border border-hair/80 bg-soft/40 px-3 py-2">
          <span className="text-mist">{s.weekday_label ?? 'Day'}</span> · {s.start_time.slice(0, 5)}{' '}
          - {s.end_time.slice(0, 5)} <span className="text-[11px] text-muted">({s.timezone})</span>
        </li>
      ))}
    </ul>
  );
}
