import { useCallback, useEffect, useRef, useState } from 'react';
import { useConnectionStore } from '../../auth/connectionStore';
import {
  getMemory,
  isFresh,
  readQuery,
  subscribeQuery,
  writeQuery,
  type CacheRecord,
} from './queryClient';

export type CachedQueryState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
  /** True when the visible data came from cache (memory/IDB), not this mount's network. */
  fromCache: boolean;
  /** True when serving cache because the browser is offline or the fetch failed. */
  stale: boolean;
  updatedAt: number | null;
  refresh: (opts?: { force?: boolean }) => Promise<void>;
  setData: (data: T | null) => Promise<void>;
};

/**
 * Cached query: hydrate from memory/IDB, skip network when fresh, keep showing
 * cached data offline with an explicit stale badge signal.
 */
export function useCachedQuery<T>(opts: {
  key: string | null;
  staleTimeMs: number;
  enabled?: boolean;
  fetcher: () => Promise<T>;
}): CachedQueryState<T> {
  const { key, staleTimeMs, fetcher, enabled = true } = opts;
  const online = useConnectionStore((s) => s.browserOnline);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const [data, setDataState] = useState<T | null>(() =>
    key ? (getMemory<T>(key)?.data ?? null) : null,
  );
  const [updatedAt, setUpdatedAt] = useState<number | null>(() =>
    key ? (getMemory<T>(key)?.updatedAt ?? null) : null,
  );
  const [fromCache, setFromCache] = useState(() => Boolean(key && getMemory(key)));
  const [stale, setStale] = useState(false);
  const [loading, setLoading] = useState(() => Boolean(enabled && key && !getMemory(key)));
  const [error, setError] = useState<string | null>(null);

  const applyRecord = useCallback((record: CacheRecord<T>, meta: { fromCache: boolean; stale: boolean }) => {
    setDataState(record.data);
    setUpdatedAt(record.updatedAt);
    setFromCache(meta.fromCache);
    setStale(meta.stale);
  }, []);

  const setData = useCallback(
    async (next: T | null) => {
      if (!key) {
        setDataState(null);
        setUpdatedAt(null);
        return;
      }
      if (next == null) {
        setDataState(null);
        setUpdatedAt(null);
        setFromCache(false);
        setStale(false);
        return;
      }
      const record = await writeQuery(key, next);
      applyRecord(record, { fromCache: false, stale: false });
    },
    [key, applyRecord],
  );

  const refresh = useCallback(
    async (opts?: { force?: boolean }) => {
      if (!key || !enabled) {
        setLoading(false);
        return;
      }

      const existing =
        getMemory<T>(key) ?? ((await readQuery<T>(key)) as CacheRecord<T> | null);
      if (existing) {
        const fresh = isFresh(existing.updatedAt, staleTimeMs);
        applyRecord(existing, {
          fromCache: true,
          stale: !fresh || !online,
        });
        if (!online) {
          setLoading(false);
          setError(null);
          setStale(true);
          return;
        }
        if (fresh && !opts?.force) {
          setLoading(false);
          setError(null);
          return;
        }
      } else if (!online) {
        setLoading(false);
        setError('You’re offline and nothing is cached yet.');
        return;
      }

      setLoading(true);
      try {
        const next = await fetcherRef.current();
        const record = await writeQuery(key, next);
        applyRecord(record, { fromCache: false, stale: false });
        setError(null);
      } catch (err) {
        if (existing) {
          applyRecord(existing, { fromCache: true, stale: true });
          setError(null);
        } else {
          setError(err instanceof Error ? err.message : 'Request failed.');
        }
      } finally {
        setLoading(false);
      }
    },
    [key, enabled, staleTimeMs, online, applyRecord],
  );

  useEffect(() => {
    if (!key || !enabled) {
      setDataState(null);
      setUpdatedAt(null);
      setLoading(false);
      return;
    }
    void refresh();
    return subscribeQuery(key, () => {
      const mem = getMemory<T>(key);
      if (mem) {
        applyRecord(mem, {
          fromCache: true,
          stale: !isFresh(mem.updatedAt, staleTimeMs) || !useConnectionStore.getState().browserOnline,
        });
      }
    });
  }, [key, enabled, refresh, applyRecord, staleTimeMs]);

  return {
    data,
    loading,
    error,
    fromCache,
    stale,
    updatedAt,
    refresh,
    setData,
  };
}
