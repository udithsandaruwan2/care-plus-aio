import type { MatchHit, MatchResponse } from '@care-plus/api-client';

function FactorBar({ label, value, className }: { label: string; value: number; className: string }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="flex items-center gap-2 text-[10px]">
      <span className="w-10 shrink-0 text-muted">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-void/60">
        <div className={`h-full rounded-full ${className}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-7 text-right font-mono text-muted">{pct}</span>
    </div>
  );
}

function MatchCard({ hit }: { hit: MatchHit }) {
  const km =
    hit.distance_m != null && Number.isFinite(hit.distance_m)
      ? `${(hit.distance_m / 1000).toFixed(1)} km`
      : null;

  return (
    <article className="animate-[fadeIn_320ms_ease] rounded-2xl border border-hair bg-panel/80 p-4 text-left backdrop-blur-md">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-display text-sm text-mist">
            <span className="mr-2 font-mono text-cyan">#{hit.rank}</span>
            {hit.display_name}
          </p>
          <p className="mt-0.5 text-xs text-muted">
            {(hit.specialties || []).slice(0, 3).join(' · ') || 'General care'}
            {hit.languages?.length ? ` · ${hit.languages.join('/')}` : ''}
            {km ? ` · ${km}` : ''}
          </p>
        </div>
        <div className="text-right">
          <p className="font-mono text-lg text-mint">{(hit.score * 100).toFixed(0)}</p>
          <p className="text-[10px] uppercase tracking-wide text-muted">score</p>
        </div>
      </div>

      <div className="mt-3 space-y-1">
        <FactorBar label="CBF" value={hit.breakdown.cbf} className="bg-cyan" />
        <FactorBar label="CF" value={hit.breakdown.cf} className="bg-violet" />
        <FactorBar label="Geo" value={hit.breakdown.geo} className="bg-mint" />
        <FactorBar label="Trust" value={hit.breakdown.trust} className="bg-amber" />
      </div>

      <p className="mt-3 text-xs text-cyan/90">{hit.explanation}</p>

      <button
        type="button"
        className="mt-3 w-full rounded-full border border-cyan/40 px-3 py-1.5 text-xs text-cyan transition hover:bg-cyan/10"
        onClick={() => {
          // Hire lifecycle lands in Step 23 (CareRequest).
          window.alert('Request caregiver — coming in the hire flow (Step 23).');
        }}
      >
        Request this caregiver
      </button>
    </article>
  );
}

/** Ranked VEHMF cards with score breakdown, XAI, and latency badge. */
export function MatchResultCards({ match }: { match: MatchResponse }) {
  if (!match.results.length) {
    return <p className="mt-4 text-center text-sm text-muted">No caregivers matched yet.</p>;
  }
  return (
    <div className="mt-6 w-full max-w-md space-y-3">
      <div className="flex items-center justify-between gap-2 px-1">
        <p className="font-display text-sm tracking-wide text-mist">Best matches</p>
        <span className="rounded-full border border-mint/40 px-2.5 py-0.5 font-mono text-[11px] text-mint">
          {match.latency_ms} ms
        </span>
      </div>
      {match.results.map((hit) => (
        <MatchCard key={hit.caregiver_id} hit={hit} />
      ))}
    </div>
  );
}
