import { describe, expect, it } from 'vitest';
import { wsOrigin } from './wsOrigin';

describe('wsOrigin', () => {
  it('strips a trailing /ws so Live is not double-prefixed', () => {
    expect(wsOrigin('wss://careplus.udithsandaruwan.com/ws')).toBe(
      'wss://careplus.udithsandaruwan.com',
    );
    expect(wsOrigin('ws://localhost:8000/ws/')).toBe('ws://localhost:8000');
  });

  it('keeps a host-only base', () => {
    expect(wsOrigin('wss://careplus.udithsandaruwan.com')).toBe(
      'wss://careplus.udithsandaruwan.com',
    );
  });
});
