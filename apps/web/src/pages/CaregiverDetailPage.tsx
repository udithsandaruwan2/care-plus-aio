import { FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import type { CaregiverDetail } from '@care-plus/api-client';
import { ApiError } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { clearBookingIntent, readBookingIntent, saveBookingIntent } from '../booking/intent';
import { BackLink } from '../components/ui/BackLink';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { PageHeader } from '../components/ui/PageHeader';

function formatReviewDate(value?: string) {
  if (!value) return '';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString();
}

export function CaregiverDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [profile, setProfile] = useState<CaregiverDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [requesting, setRequesting] = useState(false);
  const [requestSent, setRequestSent] = useState(false);
  const [resumeHint, setResumeHint] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [message, setMessage] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    const pk = Number(id);
    if (!Number.isFinite(pk) || pk <= 0) {
      setError('Invalid caregiver link.');
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .caregiver(pk)
      .then((data) => {
        if (!cancelled) setProfile(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setProfile(null);
          setError(err instanceof Error ? err.message : 'Could not load caregiver.');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

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
      await api.createCareRequest({
        caregiver_id: profile.id,
        message: message.trim() || undefined,
      });
      setRequestSent(true);
      clearBookingIntent();
      navigate('/requests');
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
    <div>
      <BackLink to="/caregivers">Caregivers</BackLink>
      <div className="mt-4">
        <PageHeader
          eyebrow="Caregiver profile"
          title={loading ? 'Caregiver' : profile?.display_name || 'Caregiver'}
          subtitle={
            profile
              ? `${profile.approximate_area || profile.city || 'Sri Lanka'} · ${
                  profile.is_available === false ? 'currently unavailable' : 'available'
                }`
              : undefined
          }
        />
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

          <div className="flex flex-wrap items-start justify-between gap-4">
            <p className="max-w-2xl text-sm leading-relaxed text-mist/90">
              {profile.bio || 'Community caregiver on Care Plus.'}
            </p>
            <div className="text-right">
              <p className="text-3xl text-mint">{Math.round((profile.trust_score || 0) * 100)}</p>
              <p className="text-[11px] uppercase tracking-wide text-muted">trust</p>
            </div>
          </div>

          <dl className="grid gap-6 sm:grid-cols-2">
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-muted">Languages</dt>
              <dd className="mt-1 text-sm text-cyan">{(profile.languages || []).join(' · ') || '—'}</dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-muted">Care levels</dt>
              <dd className="mt-1 text-sm text-mint">{(profile.care_levels || []).join(' · ') || '—'}</dd>
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
            <div className="flex flex-wrap gap-2">
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
              <p className="mt-2 text-sm text-muted">No approved reviews yet.</p>
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
    </div>
  );
}

function AvailabilitySlots({
  caregiverId,
}: {
  caregiverId: number;
  caregiverName?: string;
}) {
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

  if (!slots.length) return <p className="mt-2 text-sm text-muted">No published slots yet.</p>;

  return (
    <ul className="mt-3 space-y-2 text-sm text-muted">
      {slots.map((s) => (
        <li key={s.id} className="rounded-xl border border-hair/80 bg-soft/40 px-3 py-2">
          <span className="text-mist">{s.weekday_label ?? 'Day'}</span> · {s.start_time.slice(0, 5)}{' '}
          - {s.end_time.slice(0, 5)}{' '}
          <span className="text-[11px] text-muted">({s.timezone})</span>
        </li>
      ))}
    </ul>
  );
}
