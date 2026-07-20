import { Link } from 'react-router-dom';
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

function RankChange({ hit }: { hit: MatchHit }) {
  if (hit.rank_delta == null || hit.previous_rank == null || hit.rank_delta === 0) {
    if (hit.previous_rank == null && hit.rank_delta == null) return null;
    if (hit.rank_delta === 0) {
      return <span className="ml-1 font-mono text-[10px] text-muted">· same</span>;
    }
  }
  const delta = hit.rank_delta ?? 0;
  if (delta > 0) {
    return (
      <span className="ml-1 font-mono text-[10px] text-mint" title={`was #${hit.previous_rank}`}>
        ↑{delta}
      </span>
    );
  }
  if (delta < 0) {
    return (
      <span className="ml-1 font-mono text-[10px] text-amber" title={`was #${hit.previous_rank}`}>
        ↓{Math.abs(delta)}
      </span>
    );
  }
  return null;
}

function MatchCard({ hit }: { hit: MatchHit }) {
  const km =
    hit.distance_m != null && Number.isFinite(hit.distance_m)
      ? `${(hit.distance_m / 1000).toFixed(1)} km`
      : null;
  const changed = hit.previous_rank != null && hit.previous_rank !== hit.rank;

  return (
    <article
      className={`animate-[fadeIn_320ms_ease] rounded-2xl border bg-panel/80 p-4 text-left backdrop-blur-md ${
        changed ? 'border-mint/50 ring-1 ring-mint/20' : 'border-hair'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-display text-sm text-mist">
            <span className="mr-2 font-mono text-cyan">#{hit.rank}</span>
            {hit.display_name}
            <RankChange hit={hit} />
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

      <div className="mt-3 flex flex-col gap-2">
        <Link
          to={`/caregivers/${hit.caregiver_id}`}
          className="block w-full rounded-full border border-hair px-3 py-1.5 text-center text-xs text-muted transition hover:border-cyan hover:text-cyan"
        >
          View profile
        </Link>
        <button
          type="button"
          className="w-full rounded-full border border-cyan/40 px-3 py-1.5 text-xs text-cyan transition hover:bg-cyan/10"
          onClick={() => {
            // Hire lifecycle lands in Step 23 (CareRequest).
            window.alert('Request caregiver — coming in the hire flow (Step 23).');
          }}
        >
          Request this caregiver
        </button>
      </div>
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
        <p className="font-display text-sm tracking-wide text-mist">
          {match.refined ? 'Updated matches' : 'Best matches'}
        </p>
        <span className="rounded-full border border-mint/40 px-2.5 py-0.5 font-mono text-[11px] text-mint">
          {match.latency_ms} ms
        </span>
      </div>
      {match.results.map((hit) => (
        <MatchCard key={`${match.request_id}-${hit.caregiver_id}`} hit={hit} />
      ))}
    </div>
  );
}
