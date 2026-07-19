import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { CaregiverProfile } from '@care-plus/api-client';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { CaregiverMap } from '../components/CaregiverMap';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';

const LANG_CHIPS = ['Sinhala', 'Tamil', 'English'] as const;
const SPECIALTY_CHIPS = ['diabetes', 'hypertension', 'elderly care', 'dementia', 'asthma'] as const;

type Filters = {
  q: string;
  language: string;
  specialty: string;
  availableOnly: boolean;
};

const emptyFilters: Filters = {
  q: '',
  language: '',
  specialty: '',
  availableOnly: true,
};

export function BrowseCaregiversPage() {
  const { logout } = useAuth();
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [draftQ, setDraftQ] = useState('');
  const [rows, setRows] = useState<CaregiverProfile[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .caregivers({
        q: filters.q || undefined,
        language: filters.language || undefined,
        specialty: filters.specialty || undefined,
        available: filters.availableOnly ? 'true' : undefined,
        page_size: 50,
      })
      .then((res) => {
        if (cancelled) return;
        setRows(res.results);
        setCount(res.count);
        setSelectedId((prev) =>
          res.results.some((r) => r.id === prev) ? prev : (res.results[0]?.id ?? null),
        );
      })
      .catch((err) => {
        if (cancelled) return;
        setRows([]);
        setCount(0);
        setError(err instanceof Error ? err.message : 'Could not load caregivers.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filters]);

  const selected = useMemo(
    () => rows.find((r) => r.id === selectedId) ?? null,
    [rows, selectedId],
  );

  function toggleChip<K extends 'language' | 'specialty'>(key: K, value: string) {
    setFilters((f) => ({ ...f, [key]: f[key] === value ? '' : value }));
  }

  return (
    <AtmosphereShell>
      <main className="mx-auto flex min-h-full max-w-5xl flex-col px-6 py-10">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-display text-sm uppercase tracking-[0.2em] text-cyan">Browse</p>
            <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-mist sm:text-4xl">
              Caregivers
            </h1>
            <p className="mt-2 max-w-xl text-sm text-muted">
              Search the directory by language and specialty — map pins update with your filters.
            </p>
          </div>
          <div className="flex gap-2">
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

        <form
          className="mt-8 flex flex-col gap-3 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            setFilters((f) => ({ ...f, q: draftQ.trim() }));
          }}
        >
          <input
            value={draftQ}
            onChange={(e) => setDraftQ(e.target.value)}
            placeholder="Search name, city, specialty…"
            className="min-w-0 flex-1 rounded-full border border-hair bg-void/40 px-4 py-2.5 text-sm text-mist outline-none ring-cyan/40 placeholder:text-muted focus:ring-2"
          />
          <button
            type="submit"
            className="rounded-full bg-cyan/90 px-5 py-2.5 text-sm font-medium text-void transition hover:bg-cyan"
          >
            Search
          </button>
        </form>

        <div className="mt-4 flex flex-wrap gap-2">
          {LANG_CHIPS.map((lang) => (
            <button
              key={lang}
              type="button"
              onClick={() => toggleChip('language', lang)}
              className={`rounded-full border px-3 py-1 text-xs transition ${
                filters.language === lang
                  ? 'border-cyan text-cyan'
                  : 'border-hair text-muted hover:border-cyan/40'
              }`}
            >
              {lang}
            </button>
          ))}
          <span className="mx-1 self-center text-hair">|</span>
          {SPECIALTY_CHIPS.map((sp) => (
            <button
              key={sp}
              type="button"
              onClick={() => toggleChip('specialty', sp)}
              className={`rounded-full border px-3 py-1 text-xs transition ${
                filters.specialty === sp
                  ? 'border-mint text-mint'
                  : 'border-hair text-muted hover:border-mint/40'
              }`}
            >
              {sp}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setFilters((f) => ({ ...f, availableOnly: !f.availableOnly }))}
            className={`rounded-full border px-3 py-1 text-xs transition ${
              filters.availableOnly
                ? 'border-amber text-amber'
                : 'border-hair text-muted hover:border-amber/40'
            }`}
          >
            Available only
          </button>
          {(filters.q || filters.language || filters.specialty || !filters.availableOnly) && (
            <button
              type="button"
              onClick={() => {
                setDraftQ('');
                setFilters(emptyFilters);
              }}
              className="rounded-full border border-hair px-3 py-1 text-xs text-muted hover:text-rose"
            >
              Clear
            </button>
          )}
        </div>

        <p className="mt-3 text-xs text-muted" aria-live="polite">
          {loading ? 'Loading…' : `${count} caregiver${count === 1 ? '' : 's'}`}
          {filters.language ? ` · ${filters.language}` : ''}
          {filters.specialty ? ` · ${filters.specialty}` : ''}
        </p>

        {error && (
          <p className="mt-4 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
            {error}
          </p>
        )}

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <CaregiverMap caregivers={rows} selectedId={selectedId} onSelect={setSelectedId} />

          <div className="flex max-h-[28rem] flex-col gap-2 overflow-y-auto pr-1">
            {!loading && !error && rows.length === 0 && (
              <p className="rounded-xl border border-hair bg-panel/60 px-4 py-8 text-center text-sm text-muted">
                No caregivers match these filters. Try clearing specialty or language.
              </p>
            )}
            {rows.map((cg) => {
              const active = cg.id === selectedId;
              return (
                <button
                  key={cg.id}
                  type="button"
                  onClick={() => setSelectedId(cg.id)}
                  className={`w-full rounded-xl border px-4 py-3 text-left transition ${
                    active
                      ? 'border-cyan/60 bg-cyan/5'
                      : 'border-hair bg-panel/50 hover:border-cyan/30'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-display text-sm text-mist">{cg.display_name}</p>
                      <p className="mt-0.5 text-xs text-muted">
                        {(cg.specialties || []).slice(0, 3).join(' · ') || 'General care'}
                        {cg.city ? ` · ${cg.city}` : ''}
                      </p>
                      <p className="mt-1 text-[11px] text-violet">
                        {(cg.languages || []).join(' / ')}
                        {cg.is_available === false ? ' · unavailable' : ''}
                      </p>
                    </div>
                    <p className="font-mono text-sm text-mint">
                      {Math.round((cg.trust_score || 0) * 100)}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {selected && (
          <div className="mt-6 rounded-2xl border border-hair bg-panel/70 p-5 backdrop-blur-md">
            <p className="font-display text-lg text-mist">{selected.display_name}</p>
            <p className="mt-1 text-sm text-muted">
              {selected.bio || 'Community caregiver on Care Plus.'}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Link
                to={`/caregivers/${selected.id}`}
                className="rounded-full bg-cyan/90 px-4 py-2 text-sm font-medium text-void transition hover:bg-cyan"
              >
                View full profile
              </Link>
              <Link
                to="/"
                className="rounded-full border border-hair px-4 py-2 text-sm text-muted transition hover:border-cyan hover:text-cyan"
              >
                Match with Serah
              </Link>
            </div>
          </div>
        )}
      </main>
    </AtmosphereShell>
  );
}
