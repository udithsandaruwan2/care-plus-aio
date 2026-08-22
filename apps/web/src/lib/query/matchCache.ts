/** Persist / hydrate last VEHMF match for offline replay (Step 94). */

import type { MatchResponse } from '@care-plus/api-client';
import type { IntentDraft } from '@care-plus/core';
import { readQuery, writeQuery, removeQuery } from './queryClient';
import { queryKeys, STALE_MS } from './keys';

type CachedMatch = { match: MatchResponse; intent?: IntentDraft };

/** Records written before Step 94b hold a bare MatchResponse. */
function unwrap(data: MatchResponse | CachedMatch): CachedMatch {
  return 'match' in data ? data : { match: data };
}

export async function persistLastMatch(
  userId: number | string,
  match: MatchResponse | null,
  intent?: IntentDraft,
): Promise<void> {
  const key = queryKeys.lastMatch(userId);
  if (!match) {
    await removeQuery(key);
    return;
  }
  await writeQuery(key, { match, intent } satisfies CachedMatch);
}

export async function loadLastMatch(userId: number | string): Promise<
  | {
      match: MatchResponse;
      intent?: IntentDraft;
      updatedAt: number;
      stale: boolean;
    }
  | null
> {
  const record = await readQuery<MatchResponse | CachedMatch>(queryKeys.lastMatch(userId));
  if (!record) return null;
  const stale = Date.now() - record.updatedAt >= STALE_MS.match;
  const { match, intent } = unwrap(record.data);
  return { match, intent, updatedAt: record.updatedAt, stale };
}
