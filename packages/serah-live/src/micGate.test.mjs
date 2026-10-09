import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  createMicGateState,
  downsampleTo16k,
  frameRms,
  isVoicedHop,
  periodicity,
  pushMicBuffer,
  suppressNoise,
  takePcmFrames,
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

function fricative(amp) {
  const out = new Float32Array(N);
  let prev = 0;
  let seed = 3;
  for (let i = 0; i < N; i++) {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    const x = ((seed / 0x7fffffff) * 2 - 1) * amp;
    const y = x - prev;
    prev = x;
    out[i] = y * 0.5;
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
    assert.equal(pushMicBuffer(vowel(0.28), true, state), 'barge');
  });

  it('drops the speaker tail after she stops and sends a nearer voice', () => {
    const state = createMicGateState();
    const bleed = vowel(0.05);
    assert.equal(pushMicBuffer(bleed, true, state), 'drop');
    assert.equal(pushMicBuffer(bleed, true, state), 'drop');
    assert.equal(pushMicBuffer(bleed, 'echo-tail', state), 'drop');
    assert.equal(pushMicBuffer(vowel(0.28), 'echo-tail', state), 'send');
  });

  it('keeps the consonant after a vowel and still drops the inhale', () => {
    const state = createMicGateState();
    assert.equal(pushMicBuffer(fricative(0.12), false, state), 'drop');
    assert.equal(pushMicBuffer(vowel(0.06), false, state), 'send');
    assert.equal(pushMicBuffer(fricative(0.12), false, state), 'send');
    assert.equal(pushMicBuffer(breath(0.35), false, state), 'drop');
  });
});

describe('resample', () => {
  it('keeps 16 kHz and folds 48 kHz down to the model rate', () => {
    const same = downsampleTo16k([0.25, -0.25, 0.25], 16000);
    assert.equal(same.length, 3);
    assert.equal(same[0], 0.25);
    const fast = new Float32Array(4800);
    fast.fill(0.4);
    const slow = downsampleTo16k(fast, 48000);
    assert.equal(slow.length, 1600);
    assert.ok(Math.abs(slow[0] - 0.4) < 1e-6);
  });

  it('assembles a full frame across short buffers', () => {
    const first = takePcmFrames(new Float32Array(0), new Float32Array(1000), 2048);
    assert.equal(first.frames.length, 0);
    assert.equal(first.pending.length, 1000);
    const second = takePcmFrames(first.pending, new Float32Array(1500), 2048);
    assert.equal(second.frames.length, 1);
    assert.equal(second.frames[0].length, 2048);
    assert.equal(second.pending.length, 452);
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
    const memory = { x: 0, y: 0 };
    const head = suppressNoise(voice.subarray(0, 2000), 0.005, memory);
    const tail = suppressNoise(voice.subarray(2000), 0.005, memory);
    const whole = suppressNoise(voice, 0.005, { x: 0, y: 0 });
    assert.ok(head.length === 2000 && tail.length === voice.length - 2000);
    assert.ok(Math.abs((whole[2000] ?? 0) - (tail[0] ?? 0)) < 1e-4);
  });
});
