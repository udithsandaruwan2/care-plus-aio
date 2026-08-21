import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getMemory,
  isFresh,
  readQuery,
  resetQueryCacheMemory,
  writeQuery,
} from './queryClient';
import { STALE_MS } from './keys';

describe('queryClient', () => {
  beforeEach(() => {
    resetQueryCacheMemory();
    vi.stubGlobal('indexedDB', undefined);
  });

  it('keeps fresh entries in memory without needing a refetch signal', async () => {
    const record = await writeQuery('browse:test', { count: 2 });
    expect(getMemory('browse:test')?.data).toEqual({ count: 2 });
    expect(isFresh(record.updatedAt, STALE_MS.browse)).toBe(true);
    const again = await readQuery<{ count: number }>('browse:test');
    expect(again?.data.count).toBe(2);
  });

  it('marks old timestamps as stale', () => {
    expect(isFresh(Date.now() - STALE_MS.browse - 1, STALE_MS.browse)).toBe(false);
  });
});
