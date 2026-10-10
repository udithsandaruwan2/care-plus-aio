import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  fallbackVoiceAllowed,
  liveSessionOpen,
  setLiveSessionOpen,
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
});
