import { describe, expect, it } from 'vitest';
import { ApiError, NetworkError, TimeoutError } from '@care-plus/api-client';
import { classifyTurnFailure } from './turnFailure';

describe('classifyTurnFailure', () => {
  it('labels network errors for retry + auto-replay', () => {
    const f = classifyTurnFailure(new NetworkError('offline'));
    expect(f.kind).toBe('network');
    expect(f.autoReplay).toBe(true);
    expect(f.canRetry).toBe(true);
  });

  it('labels timeouts separately', () => {
    const f = classifyTurnFailure(new TimeoutError('slow', 30_000));
    expect(f.kind).toBe('timeout');
    expect(f.autoReplay).toBe(true);
  });

  it('labels 429 throttle without auto-replay', () => {
    const f = classifyTurnFailure(new ApiError('slow down', 429));
    expect(f.kind).toBe('throttle');
    expect(f.autoReplay).toBe(false);
    expect(f.canRetry).toBe(true);
  });

  it('labels consent 451', () => {
    const f = classifyTurnFailure(new ApiError('consent', 451));
    expect(f.kind).toBe('consent');
    expect(f.canRetry).toBe(false);
  });
});
