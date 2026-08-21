/**
 * In-memory query cache with IndexedDB persistence (Step 94).
 * Fresh entries skip network refetch on remount; stale/offline still render.
 */

import { idbDelete, idbGet, idbSet } from './idbStore';

export type CacheRecord<T> = {
  data: T;
  updatedAt: number;
};

type Listener = () => void;

const memory = new Map<string, CacheRecord<unknown>>();
const listeners = new Map<string, Set<Listener>>();

function notify(key: string) {
  const set = listeners.get(key);
  if (!set) return;
  for (const fn of set) fn();
}

export function subscribeQuery(key: string, listener: Listener): () => void {
  let set = listeners.get(key);
  if (!set) {
    set = new Set();
    listeners.set(key, set);
  }
  set.add(listener);
  return () => {
    set!.delete(listener);
    if (set!.size === 0) listeners.delete(key);
  };
}

export function getMemory<T>(key: string): CacheRecord<T> | null {
  return (memory.get(key) as CacheRecord<T> | undefined) ?? null;
}

export function isFresh(updatedAt: number, staleTimeMs: number): boolean {
  return Date.now() - updatedAt < staleTimeMs;
}

export async function readQuery<T>(key: string): Promise<CacheRecord<T> | null> {
  const mem = getMemory<T>(key);
  if (mem) return mem;
  const disk = await idbGet(key);
  if (!disk) return null;
  const record: CacheRecord<T> = {
    data: disk.data as T,
    updatedAt: disk.updatedAt,
  };
  memory.set(key, record as CacheRecord<unknown>);
  return record;
}

export async function writeQuery<T>(key: string, data: T): Promise<CacheRecord<T>> {
  const record: CacheRecord<T> = { data, updatedAt: Date.now() };
  memory.set(key, record as CacheRecord<unknown>);
  await idbSet({ key, data, updatedAt: record.updatedAt });
  notify(key);
  return record;
}

export async function removeQuery(key: string): Promise<void> {
  memory.delete(key);
  await idbDelete(key);
  notify(key);
}

/** Test helper — wipe memory (and optionally IndexedDB). */
export function resetQueryCacheMemory(): void {
  memory.clear();
}
