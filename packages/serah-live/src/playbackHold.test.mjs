import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  createPlaybackHold,
  createSpeakWatch,
  holdPlayback,
  holdReleaseDue,
  onSourceEnd,
  onSourceStart,
  pollSpeakingStopped,
  releasePlayback,
  resamplePlayback,
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

  it('releases if the interrupted turn never closes', () => {
    assert.equal(holdReleaseDue(2000), false);
    assert.equal(holdReleaseDue(2500), true);
  });
});

describe('resamplePlayback', () => {
  it('keeps 24 kHz and stretches a chunk onto a 48 kHz device', () => {
    const same = resamplePlayback([0.25, -0.5], 24000, 24000);
    assert.equal(same.length, 2);
    assert.equal(same[1], -0.5);
    const stretched = resamplePlayback([0, 1], 24000, 48000);
    assert.equal(stretched.length, 4);
    assert.equal(stretched[0], 0);
    assert.ok(stretched[stretched.length - 1] > 0.9);
    const flat = resamplePlayback([0.4, 0.4, 0.4, 0.4], 24000, 48000);
    assert.ok(flat.every((sample) => Math.abs(sample - 0.4) < 1e-6));
  });
});

describe('schedulePcmStart', () => {
  it('prerolls only the first chunk and starts a late one immediately', () => {
    assert.equal(schedulePcmStart(10, 10.4), 10.4);
    assert.equal(schedulePcmStart(10, 9.9), 10);
    assert.equal(schedulePcmStart(10, 0), 10.08);
  });
});

describe('speak watch', () => {
  it('does not say she stopped during a short gap between chunks', () => {
    const watch = createSpeakWatch();
    assert.equal(onSourceStart(watch), true);
    onSourceEnd(watch, 1000);
    assert.equal(pollSpeakingStopped(watch, 1100), false);
    assert.equal(onSourceStart(watch), false);
    assert.equal(watch.announced, true);
  });

  it('says she stopped after the grace when nothing follows', () => {
    const watch = createSpeakWatch();
    onSourceStart(watch);
    onSourceEnd(watch, 1000);
    assert.equal(pollSpeakingStopped(watch, 1200), true);
    assert.equal(watch.announced, false);
  });
});
