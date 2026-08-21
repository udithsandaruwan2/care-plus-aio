import { useState } from 'react';
import type { CaregiverProfile } from '@care-plus/api-client';
import { CaregiverCard } from '../components/caregivers/CaregiverCard';
import { CaregiverMap } from '../components/CaregiverMap';
import { api } from '../auth/api';
import { PublicPage } from '../components/layout/PublicPage';
import { BackLink } from '../components/ui/BackLink';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { PageHeader } from '../components/ui/PageHeader';
import { CacheSourceBadge } from '../lib/query/CacheSourceBadge';
import { warmEdgeCacheFromProfiles } from '../assistant/offlineMatch';
import { queryKeys, STALE_MS } from '../lib/query/keys';
import { useCachedQuery } from '../lib/query/useCachedQuery';

const LANG_CHIPS = ['Sinhala', 'Tamil', 'English'] as const;
const SPECIALTY_CHIPS = ['diabetes', 'hypertension', 'elderly care', 'dementia', 'asthma'] as const;

type Filters = {
  q: string;
  language: string;
  specialty: string;
  availableOnly: boolean;
};

type BrowsePayload = { results: CaregiverProfile[]; count: number };

const emptyFilters: Filters = {
  q: '',
  language: '',
  specialty: '',
  availableOnly: true,
};

export function BrowseCaregiversPage() {
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [draftQ, setDraftQ] = useState('');
  const [view, setView] = useState<'cards' | 'map'>('cards');
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const cacheKey = queryKeys.browse({
    q: filters.q || '',
    language: filters.language || '',
    specialty: filters.specialty || '',
    availableOnly: filters.availableOnly,
  });

  const query = useCachedQuery<BrowsePayload>({
    key: cacheKey,
    staleTimeMs: STALE_MS.browse,
    fetcher: async () => {
      const res = await api.caregivers({
        q: filters.q || undefined,
        language: filters.language || undefined,
        specialty: filters.specialty || undefined,
        available: filters.availableOnly ? 'true' : undefined,
        page_size: 50,
      });
      void warmEdgeCacheFromProfiles(res.results);
      return { results: res.results, count: res.count };
    },
  });

  const rows = query.data?.results ?? [];
  const count = query.data?.count ?? 0;
  const loading = query.loading && !query.data;
  const error = query.error;

  function toggleChip<K extends 'language' | 'specialty'>(key: K, value: string) {
    setFilters((f) => ({ ...f, [key]: f[key] === value ? '' : value }));
  }

  const filtersDirty =
    Boolean(filters.q || filters.language || filters.specialty) || !filters.availableOnly;

  return (
    <PublicPage>
      <BackLink to="/">Home</BackLink>
      <div className="mt-4 flex flex-wrap items-start justify-between gap-3">
        <PageHeader
          eyebrow="Caregiver directory"
          title="Find your caregiver match"
          subtitle="Browse verified caregivers by language, specialty, and availability across Sri Lanka."
        />
        <CacheSourceBadge fromCache={query.fromCache} stale={query.stale} />
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
          aria-label="Search caregivers"
        />
        <Button type="submit">Search</Button>
      </form>

      <div className="mt-4 flex flex-wrap gap-2">
        {LANG_CHIPS.map((lang) => (
          <button
            key={lang}
            type="button"
            aria-pressed={filters.language === lang}
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
            aria-pressed={filters.specialty === sp}
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
          aria-pressed={filters.availableOnly}
          onClick={() => setFilters((f) => ({ ...f, availableOnly: !f.availableOnly }))}
          className={`rounded-full border px-3 py-1 text-xs transition ${
            filters.availableOnly
              ? 'border-amber text-amber'
              : 'border-hair text-muted hover:border-amber/40'
          }`}
        >
          Available only
        </button>
        {filtersDirty && (
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

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted" aria-live="polite">
          {loading ? 'Loading caregivers…' : `${count} caregiver${count === 1 ? '' : 's'}`}
        </p>
        <div className="flex gap-1 rounded-full border border-hair p-1">
          {(['cards', 'map'] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              aria-pressed={view === mode}
              onClick={() => setView(mode)}
              className={`rounded-full px-3 py-1 text-xs capitalize transition ${
                view === mode ? 'bg-cyan text-inverse' : 'text-muted hover:text-mist'
              }`}
            >
              {mode}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className="mt-4 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
          {error}
        </p>
      )}

      {loading && (
        <div className="mt-6 grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className="h-64 animate-pulse rounded-2xl border border-hair bg-panel/60"
            />
          ))}
        </div>
      )}

      {!loading && !error && rows.length === 0 && (
        <p className="mt-10 rounded-2xl border border-hair bg-panel px-6 py-10 text-center text-sm text-muted">
          No caregivers match. Try another city (e.g. Colombo, Kandy), clear language/specialty, or
          turn off “Available only”.
        </p>
      )}

      {!loading && rows.length > 0 && view === 'cards' && (
        <div className="mt-6 grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {rows.map((cg) => (
            <CaregiverCard key={cg.id} caregiver={cg} onHover={setSelectedId} />
          ))}
        </div>
      )}

      {!loading && rows.length > 0 && view === 'map' && (
        <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_1fr]">
          <CaregiverMap caregivers={rows} selectedId={selectedId} onSelect={setSelectedId} />
          <div className="max-h-[40rem] space-y-5 overflow-y-auto pr-1">
            {rows.map((cg) => (
              <CaregiverCard key={cg.id} caregiver={cg} onHover={setSelectedId} />
            ))}
          </div>
        </div>
      )}
    </PublicPage>
  );
}
