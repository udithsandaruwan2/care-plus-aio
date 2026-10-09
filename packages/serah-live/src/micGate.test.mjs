import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  createMicGateState,
  frameRms,
  isVoicedHop,
  periodicity,
  pushMicBuffer,
  suppressNoise,
} from '../.test-out/micGate.js';

const N = 4096;
const RATE = 16000;

function vowel(amp) {
  const out = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    const t = i / RATE;
    out[i] =
      amp *
      (0.65 * Math.sin(2 * Math.PI * 140 * t) + 0.35 * Math.sin(2 * Math.PI * 280 * t));
  }
  return out;
}

function breath(amp) {
  const out = new Float32Array(N);
  let y = 0;
  let seed = 17;
  for (let i = 0; i < N; i++) {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    const x = ((seed / 0x7fffffff) * 2 - 1) * amp;
    y = y * 0.97 + x * 0.03;
    out[i] = y;
  }
  return out;
}

describe('pushMicBuffer', () => {
  it('drops silence and a loud inhale', () => {
    assert.equal(pushMicBuffer(new Float32Array(N), false, createMicGateState()), 'drop');
    const inhale = breath(0.35);
    assert.ok(frameRms(inhale) > 0.02, 'inhale is louder than the old level gate');
    assert.equal(isVoicedHop(inhale.subarray(0, 512)), false);
    assert.equal(pushMicBuffer(inhale, false, createMicGateState()), 'drop');
  });

  it('sends a vowel even when it is quieter than a breath', () => {
    const voice = vowel(0.06);
    assert.ok(periodicity(voice.subarray(0, 512)) > 0.42);
    assert.equal(pushMicBuffer(voice, false, createMicGateState()), 'send');
  });

  it('learns speaker bleed and only barges on a nearer voice', () => {
    const state = createMicGateState();
    const bleed = vowel(0.05);
    assert.equal(pushMicBuffer(bleed, true, state), 'drop');
    assert.equal(pushMicBuffer(bleed, true, state), 'drop');
    assert.equal(pushMicBuffer(bleed, true, state), 'drop');
    const barge = vowel(0.28);
    assert.equal(pushMicBuffer(barge, true, state), 'barge');
  });
});

describe('suppressNoise', () => {
  it('shrinks a noise-floor frame and keeps a loud vowel', () => {
    const quiet = breath(0.04);
    const cleaned = suppressNoise(quiet, frameRms(quiet));
    assert.ok(frameRms(cleaned) < frameRms(quiet) * 0.5);
    const voice = vowel(0.2);
    const kept = suppressNoise(voice, 0.005);
    assert.ok(frameRms(kept) > frameRms(voice) * 0.5);
  });
});
