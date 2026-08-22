import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MatchResponse } from '@care-plus/api-client';
import type { IntentDraft } from '@care-plus/core';
import { loadLastMatch, persistLastMatch } from './matchCache';
import { queryKeys, STALE_MS } from './keys';
import { resetQueryCacheMemory, writeQuery } from './queryClient';

const match = { request_id: 42, results: [] } as unknown as MatchResponse;
const intent = { condition: 'diabetes', language: 'English' } as IntentDraft;

describe('matchCache', () => {
  beforeEach(() => {
    resetQueryCacheMemory();
    vi.stubGlobal('indexedDB', undefined);
  });

  it('round-trips the match with the intent that produced it', async () => {
    await persistLastMatch(7, match, intent);
    const row = await loadLastMatch(7);
    expect(row?.match.request_id).toBe(42);
    expect(row?.intent).toEqual(intent);
    expect(row?.stale).toBe(false);
  });

  it('reads records written before intents were stored', async () => {
    await writeQuery(queryKeys.lastMatch(7), match);
    const row = await loadLastMatch(7);
    expect(row?.match.request_id).toBe(42);
    expect(row?.intent).toBeUndefined();
  });

  it('flags records older than the match staleness window', async () => {
    await persistLastMatch(7, match, intent);
    vi.spyOn(Date, 'now').mockReturnValue(Date.now() + STALE_MS.match + 1);
    expect((await loadLastMatch(7))?.stale).toBe(true);
    vi.restoreAllMocks();
  });

  it('clears the record when the match is dropped', async () => {
    await persistLastMatch(7, match, intent);
    await persistLastMatch(7, null);
    expect(await loadLastMatch(7)).toBeNull();
  });
});
