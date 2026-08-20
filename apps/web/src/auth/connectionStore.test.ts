import { describe, expect, it, beforeEach } from 'vitest';
import { useConnectionStore } from './connectionStore';

describe('connectionStore', () => {
  beforeEach(() => {
    useConnectionStore.setState({
      browserOnline: true,
      requestDegraded: false,
      kind: 'online',
    });
  });

  it('marks offline from browser events', () => {
    useConnectionStore.getState().setBrowserOnline(false);
    expect(useConnectionStore.getState().kind).toBe('offline');
  });

  it('marks degraded on network/timeout outcomes', () => {
    useConnectionStore.getState().noteRequestOutcome('timeout');
    expect(useConnectionStore.getState().kind).toBe('degraded');
    useConnectionStore.getState().noteRequestOutcome('ok');
    expect(useConnectionStore.getState().kind).toBe('online');
  });
});
