import { ApiError } from '@care-plus/api-client';
import { describe, expect, it } from 'vitest';
import {
  isAlreadyAppliedOutboxError,
  isPermanentFailure,
  newIdempotencyKey,
  outboxErrorMessage,
  PERMANENT_HTTP,
} from './flush';

describe('outbox permanent failures', () => {
  it('treats validation and 451 as permanent', () => {
    for (const status of PERMANENT_HTTP) {
      expect(isPermanentFailure(new ApiError(`HTTP ${status}`, status))).toBe(true);
    }
    expect(isPermanentFailure(new ApiError('HTTP 500', 500))).toBe(false);
    expect(isPermanentFailure(new Error('offline'))).toBe(false);
  });

  it('reads DRF list details and treats duplicate care requests as already applied', () => {
    const err = new ApiError('HTTP 400', 400, [
      'An active care request already exists for this caregiver.',
    ]);
    expect(outboxErrorMessage(err)).toMatch(/already exists/i);
    expect(isAlreadyAppliedOutboxError(err)).toBe(true);
    expect(isAlreadyAppliedOutboxError(new ApiError('HTTP 400', 400, { detail: 'bad date' }))).toBe(
      false,
    );
  });

  it('generates non-empty idempotency keys', () => {
    const a = newIdempotencyKey();
    const b = newIdempotencyKey();
    expect(a.length).toBeGreaterThan(8);
    expect(a).not.toBe(b);
  });
});
