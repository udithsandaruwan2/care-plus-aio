import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  createPlaybackHold,
  holdPlayback,
  releasePlayback,
  shouldPlayPcm,
} from '../.test-out/playbackHold.js';

describe('playback hold', () => {
  it('drops leftover audio after a barge until the turn is released', () => {
    const state = createPlaybackHold();
    assert.equal(shouldPlayPcm(state), true);
    holdPlayback(state);
    assert.equal(shouldPlayPcm(state), false);
    releasePlayback(state);
    assert.equal(shouldPlayPcm(state), true);
  });
});
