import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  createPlaybackHold,
  holdPlayback,
  releasePlayback,
  schedulePcmStart,
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

describe('schedulePcmStart', () => {
  it('chains while audio is queued and pads a gap', () => {
    assert.equal(schedulePcmStart(10, 10.4), 10.4);
    assert.equal(schedulePcmStart(10, 9.9), 10.08);
    assert.equal(schedulePcmStart(10, 0), 10.08);
  });
});
