import { ApiError } from '@care-plus/api-client';
import { describe, expect, it } from 'vitest';
import { isPermanentFailure, newIdempotencyKey, PERMANENT_HTTP } from './flush';

describe('outbox permanent failures', () => {
  it('treats validation and 451 as permanent', () => {
    for (const status of PERMANENT_HTTP) {
      expect(isPermanentFailure(new ApiError(`HTTP ${status}`, status))).toBe(true);
    }
    expect(isPermanentFailure(new ApiError('HTTP 500', 500))).toBe(false);
    expect(isPermanentFailure(new Error('offline'))).toBe(false);
  });

  it('generates non-empty idempotency keys', () => {
    const a = newIdempotencyKey();
    const b = newIdempotencyKey();
    expect(a.length).toBeGreaterThan(8);
    expect(a).not.toBe(b);
  });
});
