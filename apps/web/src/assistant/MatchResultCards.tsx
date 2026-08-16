import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { MatchHit, MatchResponse } from '@care-plus/api-client';
import { ApiError } from '@care-plus/api-client';
import { api } from '../auth/api';
import { localizeExplanation, matchUi } from './locale';
import type { UiVoiceLanguage } from './uiVoiceLanguage';
import { useAssistant } from './store';
import { speakSerah } from './useTts';

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
  canRequestCare,
  matchRunId,
  uiLanguage,
}: {
  hit: MatchHit;
  canRequestCare: boolean;
  matchRunId: number;
  uiLanguage: UiVoiceLanguage;
}) {
  const ui = matchUi(uiLanguage);
  const explanation = localizeExplanation(hit.explanation, uiLanguage);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [message, setMessage] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const km =
    hit.distance_m != null && Number.isFinite(hit.distance_m)
      ? `${(hit.distance_m / 1000).toFixed(1)} km`
      : null;
  const changed = hit.previous_rank != null && hit.previous_rank !== hit.rank;

  function startRequest() {
    if (!canRequestCare) {
      setFormError(
        'Complete your patient profile (at least 80%) before requesting care. Open Account or go to /onboarding.',
      );
      return;
    }
    if (sent || busy) return;
    setFormError(null);
    setShowForm(true);
  }

  async function onRequest() {
    if (!canRequestCare || sent || busy) return;
    setBusy(true);
    setFormError(null);
    try {
      await api.createCareRequest({
        caregiver_id: hit.caregiver_id,
        message: message.trim() || undefined,
        match_run_id: matchRunId,
        match_snapshot: {
          rank: hit.rank,
          score: hit.score,
          breakdown: hit.breakdown,
          explanation: hit.explanation,
          distance_m: hit.distance_m ?? null,
        },
      });
      setSent(true);
      setShowForm(false);
      const confirmation =
        uiLanguage === 'Sinhala'
          ? `${hit.display_name || 'මෙම caregiver'} වෙත ඉල්ලීම යැව්වා. ඔහු/ඇය පිළිතුරු දෙන තෙක් ඔබේ තත්ත්වය ගැන කෙටි update එකක් මට කියන්න.`
          : uiLanguage === 'Tamil'
            ? `${hit.display_name || 'இந்த பராமரிப்பாளர்'}-க்கு கோரிக்கை அனுப்பப்பட்டது. பதில் வரும் வரை உங்கள் நிலையைச் சுருக்கமாகச் சொல்லுங்கள்.`
            : `Request sent to ${hit.display_name || 'this caregiver'}. While they respond, tell me a quick update on how you feel.`;
      const store = useAssistant.getState();
      store.appendChat({ role: 'serah', text: confirmation, route: 'ACTION' });
      void speakSerah(confirmation, uiLanguage);
    } catch (err) {
      const msg =
        err instanceof ApiError && typeof err.body === 'object' && err.body
          ? String(
              (err.body as Record<string, unknown>).detail ||
                (err.body as Record<string, unknown>)[0] ||
                'Request failed.',
            )
          : err instanceof Error
            ? err.message
            : 'Request failed.';
      setFormError(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article
      className={`match-rail-card rounded-2xl border bg-panel p-3 text-left ${
        changed ? 'border-mint/50 ring-1 ring-mint/20' : 'border-hair'
      }`}
      style={{ animationDelay: `${Math.max(0, hit.rank - 1) * 80}ms` }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-display text-sm font-semibold text-mist">
            <span className="mr-2 font-mono text-sm text-cyan">#{hit.rank}</span>
            {hit.display_name}
            <RankChange hit={hit} />
          </p>
          <p className="mt-0.5 text-xs text-muted">
            {(hit.specialties || []).slice(0, 3).join(' · ') || 'General care'}
            {hit.languages?.length ? ` · ${hit.languages.join('/')}` : ''}
            {km ? ` · ${km}` : ''}
          </p>
        </div>
        <div className="flex h-11 w-11 flex-col items-center justify-center rounded-full border-2 border-cyan/40 bg-cyan/10">
          <p className="font-display text-base font-bold leading-none text-cyan">
            {(hit.score * 100).toFixed(0)}
          </p>
          <p className="mt-0.5 text-[8px] uppercase tracking-wide text-muted">{ui.score}</p>
        </div>
      </div>

      <div className="mt-3 space-y-1.5">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          VEHMF analysis
        </p>
        <FactorBar label="Skills (CBF)" value={hit.breakdown.cbf} className="bg-cyan" />
        <FactorBar label="History (CF)" value={hit.breakdown.cf} className="bg-violet" />
        <FactorBar label="Distance (Geo)" value={hit.breakdown.geo} className="bg-mint" />
        <FactorBar label="Trust" value={hit.breakdown.trust} className="bg-amber" />
      </div>

      <p className="mt-3 rounded-xl bg-soft px-3 py-2 text-xs text-muted">{explanation}</p>

      <div className="mt-3 flex flex-col gap-2">
        <Link
          to={`/caregivers/${hit.caregiver_id}`}
          className="block w-full rounded-xl border border-hair px-3 py-2 text-center text-xs font-semibold text-muted transition hover:border-cyan hover:text-cyan"
        >
          {ui.viewProfile}
        </Link>
        {!showForm && (
          <button
            type="button"
            disabled={!canRequestCare || busy || sent || hit.is_available === false}
            className="w-full rounded-xl bg-cyan px-3 py-2 text-xs font-semibold text-inverse transition hover:brightness-95 disabled:cursor-not-allowed disabled:bg-soft disabled:text-muted"
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
        )}
        {showForm && !sent && (
          <div className="space-y-2 rounded-xl border border-hair bg-soft p-3">
            <label className="block space-y-1">
              <span className="text-[11px] text-muted">Optional message for the caregiver</span>
              <input
                className="w-full rounded-lg border border-hair bg-elevated px-3 py-2 text-xs text-mist outline-none focus-visible:ring-2 focus-visible:ring-cyan"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
              />
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => void onRequest()}
                className="rounded-full border border-cyan/40 px-3 py-1.5 text-xs text-cyan"
              >
                {busy ? 'Sending…' : 'Send request'}
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="rounded-full border border-hair px-3 py-1.5 text-xs text-muted"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
        {formError && (
          <p className="text-[11px] text-rose" role="alert">
            {formError}
          </p>
        )}
      </div>
    </article>
  );
}

/** Ranked VEHMF cards with score breakdown, XAI, and latency badge. */
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
  if (!match.results.length) {
    return <p className="mt-4 text-center text-sm text-muted">{ui.noMatches}</p>;
  }
  const heading = match.refined
    ? uiLanguage === 'Sinhala'
      ? 'යාවත්කාලීන ගැලපීම්'
      : uiLanguage === 'Tamil'
        ? 'புதுப்பிக்கப்பட்ட பொருத்தங்கள்'
        : 'Updated matches'
    : ui.title;

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
      {match.results.map((hit) => (
        <MatchCard
          key={`${match.request_id}-${hit.caregiver_id}`}
          hit={hit}
          canRequestCare={canRequestCare}
          matchRunId={match.request_id}
          uiLanguage={uiLanguage}
        />
      ))}
    </section>
  );
}
