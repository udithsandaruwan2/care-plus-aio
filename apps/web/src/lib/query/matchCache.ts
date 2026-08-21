/** Persist / hydrate last VEHMF match for offline replay (Step 94). */

import type { MatchResponse } from '@care-plus/api-client';
import { readQuery, writeQuery, removeQuery } from './queryClient';
import { queryKeys, STALE_MS } from './keys';

export async function persistLastMatch(
  userId: number | string,
  match: MatchResponse | null,
): Promise<void> {
  const key = queryKeys.lastMatch(userId);
  if (!match) {
    await removeQuery(key);
    return;
  }
  await writeQuery(key, match);
}

export async function loadLastMatch(
  userId: number | string,
): Promise<{ match: MatchResponse; updatedAt: number; stale: boolean } | null> {
  const record = await readQuery<MatchResponse>(queryKeys.lastMatch(userId));
  if (!record) return null;
  const stale = Date.now() - record.updatedAt >= STALE_MS.match;
  return { match: record.data, updatedAt: record.updatedAt, stale };
}
