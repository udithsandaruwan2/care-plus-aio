import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { CaregiverProfile } from '@care-plus/api-client';
import { CaregiverMap } from '../components/CaregiverMap';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { BackLink } from '../components/ui/BackLink';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { PageHeader } from '../components/ui/PageHeader';

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
  const { user } = useAuth();
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
    <div>
      <BackLink to="/">Home</BackLink>
      <div className="mt-4">
        <PageHeader
          eyebrow="Caregiver directory"
          title="Find your caregiver match"
          subtitle="Explore by language, specialty, and current availability across Sri Lanka."
        />
      </div>

      <form
        className="mt-6 flex flex-col gap-3 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          setFilters((f) => ({ ...f, q: draftQ.trim() }));
        }}
      >
        <Input
          value={draftQ}
          onChange={(e) => setDraftQ(e.target.value)}
          placeholder="Search name, city (Colombo…), specialty…"
          className="min-w-0 flex-1"
        />
        <Button type="submit">Search</Button>
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
      </p>

      {error && (
        <p className="mt-4 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
          {error}
        </p>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <CaregiverMap caregivers={rows} selectedId={selectedId} onSelect={setSelectedId} />

        <div className="max-h-[35rem] space-y-2 overflow-y-auto rounded-[1.5rem] border border-hair bg-panel/50 p-3">
          {!loading && !error && rows.length === 0 && (
            <p className="px-4 py-8 text-center text-sm text-muted">
              No caregivers match. Try another city (e.g. Colombo, Kandy), clear language/specialty,
              or turn off “Available only”.
            </p>
          )}
          {rows.map((cg) => {
            const active = cg.id === selectedId;
            return (
              <button
                key={cg.id}
                type="button"
                onClick={() => setSelectedId(cg.id)}
                className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                  active
                    ? 'border-cyan/60 bg-cyan/10'
                    : 'border-hair bg-soft/40 hover:border-cyan/30'
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
                  <p className="text-sm text-mint">{Math.round((cg.trust_score || 0) * 100)}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {selected && (
        <div className="mt-6 rounded-[1.5rem] border border-hair bg-panel/60 p-5">
          <p className="font-display text-lg text-mist">{selected.display_name}</p>
          <p className="mt-1 text-sm text-muted">{selected.bio || 'Community caregiver on Care Plus.'}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link to={`/caregivers/${selected.id}`}>
              <Button>View full profile</Button>
            </Link>
            {user && (
              <Link to="/app">
                <Button tone="ghost">Ask Serah</Button>
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
