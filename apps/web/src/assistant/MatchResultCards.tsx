import { useState } from 'react';
import type { MatchHit, MatchResponse } from '@care-plus/api-client';
import { Avatar } from '../components/ui/Avatar';
import { localizeExplanation, matchUi } from './locale';
import type { UiVoiceLanguage } from './uiVoiceLanguage';
import { useAssistant } from './store';
import { speakSerah } from './useTts';
import { comparativeMatchLine } from './compareMatch';
import { executeSerahAction } from './executeSerahAction';

function FactorBar({
  label,
  value,
  className,
}: {
  label: string;
  value: number;
  className: string;
}) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="space-y-1" role="img" aria-label={`${label} ${pct} percent`}>
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-muted">{label}</span>
        <span className="font-semibold text-mist">{pct}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-soft" aria-hidden>
        <div className={`h-full rounded-full ${className}`} style={{ width: `${pct}%` }} />
      </div>
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

function MatchCard({
  hit,
  runnerUp,
  canRequestCare,
  matchRunId: _matchRunId,
  uiLanguage,
}: {
  hit: MatchHit;
  runnerUp?: MatchHit;
  canRequestCare: boolean;
  matchRunId: number;
  uiLanguage: UiVoiceLanguage;
}) {
  const ui = matchUi(uiLanguage);
  const explanation = localizeExplanation(hit.explanation, uiLanguage);
  const compare =
    hit.rank === 1 ? comparativeMatchLine(hit, runnerUp) : null;
  const [busy] = useState(false);
  const [sent] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [openFactors, setOpenFactors] = useState(false);
  const km =
    hit.distance_m != null && Number.isFinite(hit.distance_m)
      ? `${(hit.distance_m / 1000).toFixed(1)} km`
      : null;
  const changed = hit.previous_rank != null && hit.previous_rank !== hit.rank;

  function startRequest() {
    if (!canRequestCare) {
      const msg =
        'Complete your patient profile (at least 80%) before requesting care. Open Account or go to /onboarding.';
      setFormError(msg);
      const store = useAssistant.getState();
      const last = [...store.chat].reverse().find((m) => m.role === 'serah');
      if (last?.text !== msg) {
        store.appendChat({ role: 'serah', text: msg, route: 'ACTION' });
      }
      void speakSerah(msg, uiLanguage);
      return;
    }
    if (sent || busy) return;
    setFormError(null);
    void executeSerahAction({
      type: 'request',
      caregiver_id: hit.caregiver_id,
      rank: hit.rank,
      name_query: '',
    }).then((outcome) => {
      if (outcome && !outcome.ok) setFormError(outcome.error);
    });
  }

  return (
    <article
      className={`match-rail-card relative rounded-2xl border bg-panel p-3 text-left ${
        changed ? 'border-mint/50 ring-1 ring-mint/20' : 'border-hair'
      }`}
      style={{ animationDelay: `${Math.max(0, hit.rank - 1) * 80}ms` }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2.5">
          <Avatar name={hit.display_name} photoUrl={hit.photo_url} size="sm" />
          <div className="min-w-0">
            <p className="font-display text-sm font-semibold text-mist">
              <span className="mr-2 font-mono text-sm text-cyan">#{hit.rank}</span>
              {hit.display_name}
              <RankChange hit={hit} />
            </p>
            <p className="mt-0.5 truncate text-xs text-muted">
              {(hit.specialties || []).slice(0, 2).join(' · ') || 'General care'}
              {hit.age ? ` · ${hit.age} yrs` : ''}
              {km ? ` · ${km}` : ''}
            </p>
          </div>
        </div>
        <div className="flex h-11 w-11 shrink-0 flex-col items-center justify-center rounded-full border-2 border-cyan/40 bg-cyan/10">
          <p className="font-display text-base font-bold leading-none text-cyan">
            {Number.isFinite(hit.score) ? (hit.score * 100).toFixed(0) : '—'}
          </p>
          <p className="mt-0.5 text-[8px] uppercase tracking-wide text-muted">{ui.score}</p>
        </div>
      </div>

      <p className="mt-2 line-clamp-2 text-xs leading-snug text-mist">{explanation}</p>
      {compare ? <p className="mt-1 text-[11px] text-cyan/90">{compare}</p> : null}

      <div className="relative mt-2">
        <button
          type="button"
          className="text-[11px] font-semibold text-muted underline-offset-2 hover:text-cyan hover:underline"
          aria-expanded={openFactors}
          onClick={() => setOpenFactors((v) => !v)}
        >
          {openFactors ? 'Hide VEHMF factors' : 'Show VEHMF factors'}
        </button>
        {openFactors && hit.breakdown ? (
          <div
            className="absolute left-0 right-0 top-full z-20 mt-1 space-y-1.5 rounded-xl border border-hair bg-panel p-3 shadow-lg"
            role="region"
            aria-label="VEHMF factor breakdown"
          >
            <FactorBar label="Skills (CBF)" value={hit.breakdown.cbf} className="bg-cyan" />
            <FactorBar label="History (CF)" value={hit.breakdown.cf} className="bg-violet" />
            <FactorBar label="Distance (Geo)" value={hit.breakdown.geo} className="bg-mint" />
            <FactorBar label="Trust" value={hit.breakdown.trust} className="bg-amber" />
          </div>
        ) : null}
      </div>

      <div className="mt-3 flex gap-2">
        <button
          type="button"
          className="block min-w-0 flex-1 rounded-xl border border-hair px-3 py-2 text-center text-xs font-semibold text-muted transition hover:border-cyan hover:text-cyan"
          onClick={() => {
            const store = useAssistant.getState();
            store.setFocusedCaregiverId(hit.caregiver_id);
            store.setBookingStage('profile');
          }}
        >
          {ui.viewProfile}
        </button>
        <button
          type="button"
          disabled={!canRequestCare || busy || sent || hit.is_available === false}
          className="min-w-0 flex-1 rounded-xl bg-cyan px-3 py-2 text-xs font-semibold text-inverse transition hover:brightness-95 disabled:cursor-not-allowed disabled:bg-soft disabled:text-muted"
          onClick={startRequest}
        >
          {sent
            ? uiLanguage === 'Sinhala'
              ? 'ඉල්ලීම යැවිණි'
              : uiLanguage === 'Tamil'
                ? 'கோரிக்கை அனுப்பப்பட்டது'
                : 'Request sent'
            : busy
              ? uiLanguage === 'Sinhala'
                ? 'යවමින්…'
                : uiLanguage === 'Tamil'
                  ? 'அனுப்புகிறது…'
                  : 'Sending…'
              : canRequestCare
                ? ui.request
                : uiLanguage === 'Sinhala'
                  ? 'ඉල්ලීමට පැතිකඩ සම්පූර්ණ කරන්න'
                  : uiLanguage === 'Tamil'
                    ? 'கோரிக்கைக்கு சுயவிவரம் நிரம்பவும்'
                    : 'Complete profile to request'}
        </button>
        {formError && (
          <p className="text-[11px] text-rose" role="alert">
            {formError}
          </p>
        )}
      </div>
    </article>
  );
}

function isPresentableHit(hit: MatchHit): boolean {
  const name = (hit.display_name || '').trim();
  const letters = (name.match(/\p{L}/gu) || []).length;
  return letters >= 3 && (hit.specialties || []).length > 0;
}

/** Ranked VEHMF cards — dense lead row; factors behind disclosure (Step 87). */
export function MatchResultCards({
  match,
  canRequestCare = true,
  uiLanguage = 'English',
  id,
}: {
  match: MatchResponse;
  canRequestCare?: boolean;
  uiLanguage?: UiVoiceLanguage;
  id?: string;
}) {
  const ui = matchUi(uiLanguage);
  const results = match.results.filter(isPresentableHit);
  if (!results.length) {
    return <p className="mt-4 text-center text-sm text-muted">{ui.noMatches}</p>;
  }
  const heading = match.refined
    ? uiLanguage === 'Sinhala'
      ? 'යාවත්කාලීන ගැලපීම්'
      : uiLanguage === 'Tamil'
        ? 'புதுப்பிக்கப்பட்ட பொருத்தங்கள்'
        : 'Updated matches'
    : ui.title;
  const runnerUp = results.find((h) => h.rank === 2) ?? results[1];

  return (
    <section
      id={id}
      className="w-full space-y-3"
      role="region"
      aria-label={heading}
      aria-live="polite"
    >
      <div className="flex items-center justify-between gap-2 px-1">
        <h2 className="font-display text-sm tracking-wide text-mist">{heading}</h2>
        <span className="rounded-full border border-mint/40 px-2.5 py-0.5 font-mono text-[11px] text-mint">
          {match.latency_ms} ms
        </span>
      </div>
      {results.map((hit) => (
        <MatchCard
          key={`${match.request_id}-${hit.caregiver_id}`}
          hit={hit}
          runnerUp={hit.rank === 1 ? runnerUp : undefined}
          canRequestCare={canRequestCare}
          matchRunId={match.request_id}
          uiLanguage={uiLanguage}
        />
      ))}
    </section>
  );
}
