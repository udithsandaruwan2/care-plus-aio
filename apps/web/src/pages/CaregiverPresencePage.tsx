import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { CaregiverProfile } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { PageHeader } from '../components/ui/PageHeader';

/** Caregiver soft presence — toggle is_available (Step 20e). */
export function CaregiverPresencePage() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<CaregiverProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user?.role !== 'caregiver') {
      setLoading(false);
      setError('Only caregiver accounts can manage presence.');
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .myCaregiverProfile()
      .then((data) => {
        if (!cancelled) setProfile(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setProfile(null);
          setError(err instanceof Error ? err.message : 'Could not load your profile.');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user?.role]);

  async function toggleAvailability() {
    if (!profile || saving) return;
    const next = !profile.is_available;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.setMyAvailability(next);
      setProfile(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update availability.');
    } finally {
      setSaving(false);
    }
  }

  const available = profile?.is_available !== false;

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col">
        <PageHeader
        eyebrow="Presence"
        title="Availability"
        subtitle="Choose whether you appear available for new Serah matches across Sri Lanka."
      />

        {loading && <p className="mt-10 text-sm text-muted">Loading…</p>}

        {error && (
          <p className="mt-8 rounded-xl border border-rose/40 bg-rose/10 px-4 py-3 text-sm text-rose">
            {error}
          </p>
        )}

        {!loading && profile && (
          <section className="mt-10 space-y-6">
            <div>
              <p className="font-display text-xl text-mist">{profile.display_name}</p>
              <p className="mt-1 text-sm text-muted">
                {profile.city || 'Sri Lanka'}
                {profile.specialties?.length
                  ? ` · ${profile.specialties.slice(0, 3).join(', ')}`
                  : ''}
              </p>
            </div>

            <div className="rounded-2xl border border-hair bg-panel/80 p-5 backdrop-blur-md">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm text-mist">Open for new matches</p>
                  <p className="mt-1 text-xs text-muted">
                    When off, you stay on browse (if shown) but are hidden from Serah&apos;s match
                    rankings.
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={available}
                  disabled={saving}
                  onClick={() => void toggleAvailability()}
                  className={`relative h-8 w-14 shrink-0 rounded-full transition disabled:opacity-50 ${
                    available ? 'bg-mint/80' : 'bg-void ring-1 ring-hair'
                  }`}
                >
                  <span
                    className={`absolute top-1 left-1 h-6 w-6 rounded-full bg-mist transition ${
                      available ? 'translate-x-6' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
              <p className="mt-4 font-mono text-sm text-cyan">
                {available ? 'Available now' : 'Unavailable — hidden from Serah’s ranked matches'}
              </p>
            </div>

            <Link
              to={`/caregivers/${profile.id}`}
              className="inline-block text-sm text-cyan transition hover:underline"
            >
              View public profile →
            </Link>
          </section>
        )}
      </div>
  );
}
