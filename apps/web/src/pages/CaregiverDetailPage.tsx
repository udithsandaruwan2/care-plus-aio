import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import type { CaregiverDetail } from '@care-plus/api-client';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { usePatientProfile } from '../auth/usePatientProfile';

export function CaregiverDetailPage() {
  const { id } = useParams();
  const { logout } = useAuth();
  const { canRequestCare } = usePatientProfile();
  const [profile, setProfile] = useState<CaregiverDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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

  function onRequest() {
    if (!canRequestCare) {
      window.alert(
        'Complete your patient profile (at least 80%) before requesting care. Go to /onboarding.',
      );
      return;
    }
    window.alert('Request caregiver — hire flow lands in Step 23 (CareRequest).');
  }

  return (
    <AtmosphereShell>
      <main className="mx-auto flex min-h-full max-w-3xl flex-col px-6 py-10">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-display text-sm uppercase tracking-[0.2em] text-cyan">Profile</p>
            <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-mist sm:text-4xl">
              {loading ? 'Caregiver' : profile?.display_name || 'Caregiver'}
            </h1>
          </div>
          <div className="flex gap-2">
            <Link
              to="/caregivers"
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted transition hover:border-cyan hover:text-cyan"
            >
              Browse
            </Link>
            <Link
              to="/"
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted transition hover:border-cyan hover:text-cyan"
            >
              Neural Core
            </Link>
            <button
              type="button"
              onClick={logout}
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted transition hover:border-rose hover:text-rose"
            >
              Sign out
            </button>
          </div>
        </div>

        {loading && <p className="mt-10 text-sm text-muted">Loading profile…</p>}
        {error && (
          <p className="mt-10 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
            {error}
          </p>
        )}

        {profile && !loading && (
          <section className="mt-8 space-y-6">
            <div className="rounded-2xl border border-hair bg-panel/70 p-6 backdrop-blur-md">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="font-display text-2xl text-mist">{profile.display_name}</p>
                  <p className="mt-1 text-sm text-muted">
                    {profile.approximate_area || profile.city || 'Sri Lanka'}
                    {profile.is_available === false ? ' · currently unavailable' : ' · available'}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-mono text-3xl text-mint">
                    {Math.round((profile.trust_score || 0) * 100)}
                  </p>
                  <p className="text-[11px] uppercase tracking-wide text-muted">trust</p>
                </div>
              </div>

              <p className="mt-5 text-sm leading-relaxed text-mist/90">
                {profile.bio || 'Community caregiver on Care Plus.'}
              </p>

              <dl className="mt-6 grid gap-4 sm:grid-cols-2">
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

              <button
                type="button"
                onClick={onRequest}
                disabled={profile.is_available === false}
                className="mt-8 w-full rounded-full bg-cyan/90 px-5 py-3 text-sm font-medium text-void transition hover:bg-cyan disabled:cursor-not-allowed disabled:opacity-40"
              >
                Request this caregiver
              </button>
              <p className="mt-2 text-center text-[11px] text-muted">
                Hire / CareRequest flow ships in Step 23.
              </p>
            </div>

            <div className="rounded-2xl border border-hair bg-panel/50 p-5">
              <p className="font-display text-sm tracking-wide text-mist">Reviews</p>
              {profile.review_count > 0 && profile.reviews_teaser?.length ? (
                <ul className="mt-3 space-y-3">
                  {profile.reviews_teaser.map((r, i) => (
                    <li key={r.id ?? i} className="text-sm text-muted">
                      {r.comment || 'Rated caregiver'}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-muted">
                  No reviews yet — patient reviews land in M10.
                </p>
              )}
            </div>
          </section>
        )}
      </main>
    </AtmosphereShell>
  );
}
