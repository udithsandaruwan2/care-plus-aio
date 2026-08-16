import { useEffect, useState } from 'react';
import type { MatchResponse } from '@care-plus/api-client';
import type { UiVoiceLanguage } from './uiVoiceLanguage';
import { MatchResultCards } from './MatchResultCards';
import { matchSearchCopy } from './locale';

function SkeletonCard({ delay }: { delay: number }) {
  return (
    <article
      className="match-skeleton-card"
      style={{ animationDelay: `${delay}ms` }}
      aria-hidden
    >
      <div className="match-skeleton-line w-2/3" />
      <div className="match-skeleton-line w-1/2" />
      <div className="match-skeleton-line w-full" />
    </article>
  );
}

/** Progress + loading cards while VEHMF ranks caregivers; real cards when ready. */
export function MatchSearchPanel({
  matching,
  match,
  canRequestCare = true,
  uiLanguage = 'English',
  id,
}: {
  matching: boolean;
  match: MatchResponse | null;
  canRequestCare?: boolean;
  uiLanguage?: UiVoiceLanguage;
  id?: string;
}) {
  const copy = matchSearchCopy(uiLanguage);
  const hasResults = Boolean(match?.results?.length);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!matching) {
      setProgress(hasResults ? 100 : 0);
      return;
    }
    setProgress(14);
    const timer = window.setInterval(() => {
      setProgress((p) => Math.min(p + 7, 90));
    }, 280);
    return () => window.clearInterval(timer);
  }, [matching, hasResults]);

  if (!matching && !match) return null;

  return (
    <section
      id={id}
      className="mt-6 w-full max-w-md space-y-3"
      role="region"
      aria-label={matching ? copy.searching : copy.ready}
      aria-live="polite"
    >
      {matching ? (
        <div className="space-y-2 px-1">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-display text-sm tracking-wide text-mist">{copy.searching}</h2>
            <span className="font-mono text-[11px] text-mint">{progress}%</span>
          </div>
          <div
            className="match-search-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
            aria-label={copy.searching}
          >
            <div className="match-search-fill" style={{ width: `${progress}%` }} />
          </div>
          <p className="text-xs text-muted">{copy.keepChatting}</p>
        </div>
      ) : null}

      {matching && !hasResults ? (
        <div className="space-y-3">
          <SkeletonCard delay={0} />
          <SkeletonCard delay={120} />
          <SkeletonCard delay={240} />
        </div>
      ) : null}

      {hasResults && match ? (
        <div className={matching ? 'opacity-70' : undefined}>
          <MatchResultCards
            match={match}
            canRequestCare={canRequestCare}
            uiLanguage={uiLanguage}
          />
        </div>
      ) : null}

      {!matching && match && !hasResults ? (
        <p className="text-center text-sm text-muted">{copy.noMatches}</p>
      ) : null}
    </section>
  );
}
