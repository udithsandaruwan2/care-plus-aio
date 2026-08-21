/**
 * @vitest-environment jsdom
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useConnectionStore } from '../../auth/connectionStore';
import { getMemory, resetQueryCacheMemory, writeQuery } from './queryClient';
import { useCachedQuery } from './useCachedQuery';

describe('useCachedQuery', () => {
  beforeEach(() => {
    resetQueryCacheMemory();
    vi.stubGlobal('indexedDB', undefined);
    useConnectionStore.setState({
      browserOnline: true,
      requestDegraded: false,
      kind: 'online',
    });
  });

  it('skips network when memory entry is still fresh', async () => {
    await writeQuery('profile:1', { name: 'Ada' });
    const fetcher = vi.fn(async () => ({ name: 'Ada' }));
    const { result, rerender } = renderHook(() =>
      useCachedQuery({
        key: 'profile:1',
        staleTimeMs: 60_000,
        fetcher,
      }),
    );

    await waitFor(() => expect(result.current.data).toEqual({ name: 'Ada' }));
    expect(result.current.fromCache).toBe(true);
    const callsAfterHydrate = fetcher.mock.calls.length;

    rerender();
    await act(async () => {
      await result.current.refresh();
    });
    expect(fetcher.mock.calls.length).toBe(callsAfterHydrate);
  });

  it('serves cache offline and marks stale', async () => {
    await writeQuery('caregiver:9', { id: 9, name: 'Cached CG' });
    expect(getMemory('caregiver:9')?.data).toEqual({ id: 9, name: 'Cached CG' });
    useConnectionStore.getState().setBrowserOnline(false);
    expect(useConnectionStore.getState().browserOnline).toBe(false);

    const fetcher = vi.fn(async () => ({ id: 9, name: 'Live CG' }));
    const { result } = renderHook(() =>
      useCachedQuery({
        key: 'caregiver:9',
        staleTimeMs: 60_000,
        fetcher,
      }),
    );

    // Hydrated synchronously from memory on first paint.
    expect(result.current.data).toEqual({ id: 9, name: 'Cached CG' });

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.data).toEqual({ id: 9, name: 'Cached CG' });
    expect(result.current.fromCache).toBe(true);
    expect(result.current.stale).toBe(true);
    expect(fetcher).not.toHaveBeenCalled();
  });
});
