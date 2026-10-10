import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  fallbackVoiceAllowed,
  liveSessionOpen,
  setLiveSessionOpen,
  shouldRestartLive,
} from '../.test-out/liveSession.js';

describe('live session voice', () => {
  it('keeps fallback speech quiet only while Live is open', () => {
    setLiveSessionOpen(false);
    assert.equal(liveSessionOpen(), false);
    assert.equal(fallbackVoiceAllowed(), true);
    setLiveSessionOpen(true);
    assert.equal(fallbackVoiceAllowed(), false);
    setLiveSessionOpen(false);
    assert.equal(fallbackVoiceAllowed(), true);
  });

  it('reopens listening after an unexpected close and not after a stop', () => {
    assert.equal(shouldRestartLive(false, 0), true);
    assert.equal(shouldRestartLive(false, 1), true);
    assert.equal(shouldRestartLive(false, 2), false);
    assert.equal(shouldRestartLive(true, 0), false);
  });
});
