import type { MatchHit, SerahAction } from '@care-plus/api-client';

function normName(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

export type ResolveCaregiverOpts = {
  caregiverId?: number | null;
  rank?: number | null;
  nameQuery?: string | null;
};

/** Map caregiver_id / rank / spoken name → a VEHMF hit from ``store.match.results``. */
export function resolveCaregiverFromMatch(
  results: MatchHit[] | null | undefined,
  opts: ResolveCaregiverOpts = {},
): MatchHit | null {
  const rows = results || [];
  if (!rows.length) return null;

  if (opts.caregiverId != null) {
    const byId = rows.find((r) => r.caregiver_id === opts.caregiverId);
    if (byId) return byId;
  }

  if (opts.rank != null) {
    const byRank = rows.find((r) => r.rank === opts.rank);
    if (byRank) return byRank;
  }

  const q = normName(opts.nameQuery || '');
  if (q) {
    const qTokens = new Set(q.split(' ').filter((t) => t.length > 1));
    let best: MatchHit | null = null;
    let bestScore = 0;
    for (const row of rows) {
      const name = normName(row.display_name || '');
      if (!name) continue;
      if (name === q || name.includes(q) || q.includes(name)) return row;
      const nameTokens = new Set(name.split(' ').filter((t) => t.length > 1));
      if (!qTokens.size || !nameTokens.size) continue;
      let overlap = 0;
      for (const t of qTokens) if (nameTokens.has(t)) overlap += 1;
      const score = overlap / qTokens.size;
      if (score > bestScore && score >= 0.5) {
        bestScore = score;
        best = row;
      }
    }
    if (best) return best;
  }

  return null;
}

export function resolveCaregiverFromAction(
  results: MatchHit[] | null | undefined,
  action: Pick<SerahAction, 'caregiver_id' | 'rank' | 'name_query'> | null | undefined,
): MatchHit | null {
  if (!action) return null;
  const hit = resolveCaregiverFromMatch(results, {
    caregiverId: action.caregiver_id,
    rank: action.rank,
    nameQuery: action.name_query,
  });
  if (hit) return hit;
  // Default to top match when the action did not name anyone.
  const rows = results || [];
  if (!action.name_query && action.rank == null && action.caregiver_id == null && rows.length) {
    return rows[0] ?? null;
  }
  return null;
}
