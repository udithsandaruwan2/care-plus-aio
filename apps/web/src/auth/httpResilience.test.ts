import { describe, expect, it, vi } from 'vitest';
import {
  NetworkError,
  TimeoutError,
  backoffDelayMs,
  isIdempotentMethod,
  isNetworkError,
  isTimeoutError,
  withRetry,
} from '@care-plus/api-client';

describe('http resilience (Step 82)', () => {
  it('classifies idempotent methods for retry', () => {
    expect(isIdempotentMethod('GET')).toBe(true);
    expect(isIdempotentMethod(undefined)).toBe(true);
    expect(isIdempotentMethod('POST')).toBe(false);
  });

  it('exposes typed network and timeout errors', () => {
    expect(isNetworkError(new NetworkError())).toBe(true);
    expect(isTimeoutError(new TimeoutError('slow', 1000))).toBe(true);
    expect(isNetworkError(new Error('x'))).toBe(false);
  });

  it('backs off exponentially', () => {
    expect(backoffDelayMs(0, 300)).toBe(300);
    expect(backoffDelayMs(1, 300)).toBe(600);
    expect(backoffDelayMs(2, 300)).toBe(1200);
  });

  it('retries network failures on GET then succeeds', async () => {
    const sleep = vi.fn(async () => undefined);
    let n = 0;
    const result = await withRetry(
      'GET',
      async () => {
        n += 1;
        if (n < 3) throw new NetworkError('down');
        return 'ok';
      },
      { maxRetries: 2, sleep },
    );
    expect(result).toBe('ok');
    expect(n).toBe(3);
    expect(sleep).toHaveBeenCalledTimes(2);
  });

  it('does not retry POST network failures', async () => {
    await expect(
      withRetry('POST', async () => {
        throw new TimeoutError('hung', 50);
      }),
    ).rejects.toBeInstanceOf(TimeoutError);
  });
});
