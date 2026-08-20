import type { MatchBreakdown, MatchHit } from '@care-plus/api-client';

const FACTOR_LABELS: Record<keyof MatchBreakdown, string> = {
  cbf: 'skills',
  cf: 'similar patients',
  geo: 'distance',
  trust: 'trust',
};

/**
 * One-line reason #1 beat #2 from VEHMF factor deltas (Step 87).
 */
export function comparativeMatchLine(top: MatchHit, second: MatchHit | undefined): string | null {
  if (!second) return null;
  const keys = Object.keys(FACTOR_LABELS) as (keyof MatchBreakdown)[];
  let bestKey: keyof MatchBreakdown | null = null;
  let bestDelta = 0;
  for (const key of keys) {
    const delta = (top.breakdown[key] ?? 0) - (second.breakdown[key] ?? 0);
    if (delta > bestDelta) {
      bestDelta = delta;
      bestKey = key;
    }
  }
  if (!bestKey || bestDelta < 0.03) {
    const scoreGap = top.score - second.score;
    if (scoreGap <= 0.01) return null;
    return `Ranked above ${second.display_name} mainly on overall score (+${Math.round(scoreGap * 100)}).`;
  }
  const pct = Math.round(bestDelta * 100);
  return `Ahead of ${second.display_name} on ${FACTOR_LABELS[bestKey]} (+${pct}).`;
}
