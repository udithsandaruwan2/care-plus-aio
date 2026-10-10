import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  createPlaybackHold,
  createSpeakWatch,
  holdPlayback,
  HOLD_LIMIT_MS,
  HOLD_MAX_MS,
  holdReleaseDue,
  onSourceEnd,
  onSourceStart,
  PLAYBACK_QUANTUM,
  createPlaybackHeard,
  fallbackListenDelayMs,
  echoTailShouldInterrupt,
  micAfterBarge,
  micAfterPlaybackStop,
  notePlaybackPull,
  playbackStalled,
  pollSpeakingStopped,
  prerollCoversQuantum,
  fadeInFromSilence,
  pullPlayback,
  releasePlayback,
  replyMicMode,
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
    assert.ok(HOLD_MAX_MS > HOLD_LIMIT_MS);
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

describe('replyMicMode', () => {
  it('keeps the mic closed through a playback gap until the turn ends', () => {
    assert.equal(replyMicMode(false, false, true, 1000, 0), true);
    assert.equal(replyMicMode(false, true, false, 1000, 0), true);
    assert.equal(replyMicMode(false, false, false, 1000, 1450), 'echo-tail');
    assert.equal(replyMicMode(false, false, false, 1500, 1450), false);
    assert.equal(replyMicMode(true, true, true, 1000, 0), false);
  });
});

describe('pullPlayback', () => {
  it('plays one continuous buffer and stays silent until primed', () => {
    const queued = pullPlayback(new Float32Array([0.2, 0.4, 0.6, 0.8]), 3, true);
    assert.equal(queued.played, 3);
    assert.ok(Math.abs(queued.output[0] - 0.2) < 1e-6);
    assert.ok(Math.abs(queued.output[2] - 0.6) < 1e-6);
    assert.equal(queued.pending.length, 1);
    const next = pullPlayback(queued.pending, 3, true);
    assert.equal(next.played, 1);
    assert.ok(Math.abs(next.output[0] - 0.8) < 1e-6);
    assert.equal(next.output[1], 0);
    const held = pullPlayback(new Float32Array([0.5, 0.5]), 2, false);
    assert.equal(held.played, 0);
    assert.equal(held.output[0], 0);
    assert.equal(held.pending.length, 2);
    const edge = new Float32Array([1, 1, 1, 1]);
    fadeInFromSilence(edge, 200, 0.02);
    assert.equal(edge[0], 0);
    assert.equal(edge[edge.length - 1], 1);
    const dry = pullPlayback(new Float32Array([1, 1, 1, 1]), 8, true, 2, false);
    assert.equal(dry.played, 4);
    assert.equal(dry.output[3], 0);
    assert.equal(dry.output[2], 1);
    const resumed = pullPlayback(new Float32Array([1, 1, 1, 1]), 4, true, 3, true);
    assert.equal(resumed.output[0], 0);
    assert.equal(resumed.output[2], 1);
    const waiting = pullPlayback(new Float32Array([1, 1, 1]), 8, true, 2, true, true);
    assert.equal(waiting.played, 0);
    assert.equal(waiting.pending.length, 3);
    assert.equal(waiting.output[0], 0);
    assert.equal(prerollCoversQuantum(24000), true);
    assert.equal(prerollCoversQuantum(48000), true);
    assert.equal(PLAYBACK_QUANTUM <= Math.round(24000 * 0.08), true);
  });
});

describe('notePlaybackPull', () => {
  it('keeps a played reply audible across an empty pull', () => {
    let state = notePlaybackPull(createPlaybackHeard(), 512, false);
    state = notePlaybackPull(state, 0, false);
    assert.equal(state.heard, 512);
    assert.equal(state.lastPlayed, 512);
    assert.equal(state.afterGap, true);
    assert.equal(
      micAfterPlaybackStop({ userHasFloor: false, turnOpen: true, audible: state.heard > 0 }),
      'gap',
    );
    state = notePlaybackPull(state, 400, false);
    assert.equal(state.afterGap, false);
    assert.equal(state.heard, 912);
  });

  it('does not treat silence before the first sample as a gap', () => {
    const state = notePlaybackPull(createPlaybackHeard(), 0, false);
    assert.equal(state.heard, 0);
    assert.equal(state.afterGap, false);
    const held = notePlaybackPull(createPlaybackHeard(), 0, true);
    assert.equal(held.heard, 0);
    assert.equal(held.lastPlayed, 0);
  });
});

describe('fallbackListenDelayMs', () => {
  it('waits out her ring only when playback was just cut off', () => {
    assert.equal(fallbackListenDelayMs(true), 450);
    assert.equal(fallbackListenDelayMs(false), 0);
  });
});

describe('echoTailShouldInterrupt', () => {
  it('cuts a paused reply and leaves a finished one alone', () => {
    assert.equal(echoTailShouldInterrupt(true), true);
    assert.equal(echoTailShouldInterrupt(false), false);
  });
});

describe('micAfterBarge', () => {
  it('cuts her off but keeps the mic in the echo tail', () => {
    const now = 1000;
    const next = micAfterBarge(now);
    assert.equal(next.userHasFloor, false);
    assert.equal(next.turnOpen, false);
    assert.equal(
      replyMicMode(next.userHasFloor, false, next.turnOpen, now + 10, next.echoTailUntil),
      'echo-tail',
    );
    assert.equal(
      replyMicMode(true, false, false, now + 10, next.echoTailUntil),
      'echo-tail',
    );
    assert.equal(
      replyMicMode(true, false, false, next.echoTailUntil, next.echoTailUntil),
      false,
    );
  });
});

describe('micAfterPlaybackStop', () => {
  it('opens the mic when a reply never became audible', () => {
    assert.equal(
      micAfterPlaybackStop({ userHasFloor: false, turnOpen: true, audible: false }),
      'open',
    );
    assert.equal(
      micAfterPlaybackStop({ userHasFloor: false, turnOpen: true, audible: true }),
      'gap',
    );
    assert.equal(
      micAfterPlaybackStop({ userHasFloor: false, turnOpen: false, audible: true }),
      'tail',
    );
    assert.equal(
      micAfterPlaybackStop({ userHasFloor: true, turnOpen: true, audible: true }),
      'floor',
    );
  });
});

describe('playbackStalled', () => {
  it('releases a reply that was announced but never played', () => {
    assert.equal(playbackStalled(0, true, 999), false);
    assert.equal(playbackStalled(0, true, 1000), true);
    assert.equal(playbackStalled(10, true, 1000), false);
    assert.equal(playbackStalled(0, false, 1000), false);
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
