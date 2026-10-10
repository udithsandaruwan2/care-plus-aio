import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  createMicGateState,
  createOnsetQueue,
  downsampleTo16k,
  frameRms,
  gateLiveFrame,
  isOnsetFrame,
  isVoicedHop,
  periodicity,
  pushMicBuffer,
  suppressNoise,
  chunkLivePcm,
  LIVE_PCM_SAMPLES,
  takePcmFrames,
} from '../.test-out/micGate.js';

const N = 4096;
const RATE = 16000;

function vowel(amp) {
  const out = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    const t = i / RATE;
    out[i] =
      amp * (0.65 * Math.sin(2 * Math.PI * 140 * t) + 0.35 * Math.sin(2 * Math.PI * 280 * t));
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

  it('does not learn the user as echo, so a barge during her first words still cuts in', () => {
    const state = createMicGateState();
    const user = vowel(0.28);
    assert.equal(pushMicBuffer(user, true, state), 'drop');
    assert.equal(pushMicBuffer(user, true, state), 'drop');
    assert.equal(pushMicBuffer(user, true, state), 'barge');
  });

  it('learns speaker bleed and only barges on a nearer voice', () => {
    const state = createMicGateState();
    const bleed = vowel(0.05);
    assert.equal(pushMicBuffer(bleed, true, state), 'drop');
    assert.equal(pushMicBuffer(bleed, true, state), 'drop');
    assert.equal(pushMicBuffer(bleed, true, state), 'drop');
    assert.equal(pushMicBuffer(vowel(0.28), true, state), 'barge');
  });

  it('keeps the consonant of a barge during the echo tail and still drops her bleed', () => {
    const state = createMicGateState();
    assert.equal(pushMicBuffer(vowel(0.28), 'echo-tail', state), 'send');
    assert.equal(pushMicBuffer(fricative(0.2), 'echo-tail', state), 'send');
    assert.equal(pushMicBuffer(vowel(0.05), 'echo-tail', state), 'drop');
    assert.equal(pushMicBuffer(fricative(0.2), 'echo-tail', state), 'drop');
    assert.equal(pushMicBuffer(breath(0.35), 'echo-tail', state), 'drop');
  });

  it('drops the speaker tail after she stops and sends a nearer voice', () => {
    const state = createMicGateState();
    const bleed = vowel(0.05);
    assert.equal(pushMicBuffer(bleed, true, state), 'drop');
    assert.equal(pushMicBuffer(bleed, true, state), 'drop');
    assert.equal(pushMicBuffer(bleed, 'echo-tail', state), 'drop');
    assert.equal(pushMicBuffer(vowel(0.28), 'echo-tail', state), 'send');
  });

  it('keeps a vowel that starts in one frame and ends in the next', () => {
    const tail = new Float32Array(2048);
    const head = new Float32Array(2048);
    const voice = vowel(0.06);
    tail.set(voice.subarray(0, 1024), 1024);
    head.set(voice.subarray(0, 1024), 0);
    const state = createMicGateState();
    assert.equal(pushMicBuffer(tail, false, state), 'drop');
    assert.equal(pushMicBuffer(head, false, state), 'send');

    const broken = createMicGateState();
    assert.equal(pushMicBuffer(tail, false, broken), 'drop');
    assert.equal(pushMicBuffer(breath(0.35).subarray(0, 2048), false, broken), 'drop');
    assert.equal(pushMicBuffer(head, false, broken), 'drop');
  });

  it('barges when the nearer voice crosses a frame', () => {
    const state = createMicGateState();
    const bleed = vowel(0.05);
    assert.equal(pushMicBuffer(bleed, true, state), 'drop');
    assert.equal(pushMicBuffer(bleed, true, state), 'drop');
    const tail = new Float32Array(2048);
    const head = new Float32Array(2048);
    const user = vowel(0.28);
    tail.set(user.subarray(0, 1024), 1024);
    head.set(user.subarray(0, 1024), 0);
    assert.equal(pushMicBuffer(tail, true, state), 'drop');
    assert.equal(pushMicBuffer(head, true, state), 'barge');
  });

  it('keeps the consonant after a vowel and still drops the inhale', () => {
    const state = createMicGateState();
    assert.equal(pushMicBuffer(fricative(0.12), false, state), 'drop');
    assert.equal(pushMicBuffer(vowel(0.06), false, state), 'send');
    assert.equal(pushMicBuffer(fricative(0.12), false, state), 'send');
    assert.equal(pushMicBuffer(breath(0.35), false, state), 'drop');
  });
});

describe('gateLiveFrame', () => {
  const wire = 2048;

  it('keeps the consonant that starts a word once a vowel confirms it', () => {
    const state = createMicGateState();
    const onset = createOnsetQueue();
    const lead = fricative(0.12).subarray(0, wire);
    assert.equal(isOnsetFrame(lead), true);
    const held = gateLiveFrame(lead, false, state, onset);
    assert.deepEqual(held.audio, []);
    assert.equal(held.silenceSamples, 0);
    const opened = gateLiveFrame(vowel(0.06).subarray(0, wire), false, state, onset);
    assert.equal(opened.audio.length, 2);
    assert.equal(opened.audio[0][0], lead[0]);
    assert.equal(opened.audio[1][0], vowel(0.06)[0]);
    assert.equal(onset.frames.length, 0);
  });

  it('does not prepend an inhale, and drops a consonant that never becomes a word', () => {
    const state = createMicGateState();
    const onset = createOnsetQueue();
    const inhale = breath(0.35).subarray(0, wire);
    assert.equal(isOnsetFrame(inhale), false);
    const dropped = gateLiveFrame(inhale, false, state, onset);
    assert.equal(dropped.audio.length, 0);
    assert.equal(dropped.silenceSamples, wire);
    const voice = gateLiveFrame(vowel(0.06).subarray(0, wire), false, state, onset);
    assert.equal(voice.audio.length, 1);

    const again = createOnsetQueue();
    const quiet = createMicGateState();
    gateLiveFrame(fricative(0.12).subarray(0, wire), false, quiet, again);
    const abandoned = gateLiveFrame(inhale, false, quiet, again);
    assert.equal(abandoned.audio.length, 0);
    assert.equal(abandoned.silenceSamples, wire * 2);
    assert.equal(again.frames.length, 0);
  });

  it('keeps a consonant and vowel that share one frame, and does not keep an inhale', () => {
    const state = createMicGateState();
    const onset = createOnsetQueue();
    const mixed = new Float32Array(wire);
    mixed.set(fricative(0.12).subarray(0, wire / 2));
    mixed.set(vowel(0.06).subarray(0, wire / 2), wire / 2);
    assert.equal(pushMicBuffer(mixed, false, createMicGateState()), 'drop');
    assert.equal(isOnsetFrame(mixed), true);
    const held = gateLiveFrame(mixed, false, state, onset);
    assert.equal(held.audio.length, 0);
    assert.equal(held.silenceSamples, 0);
    const opened = gateLiveFrame(vowel(0.06).subarray(0, wire), false, state, onset);
    assert.equal(opened.audio.length, 2);
    assert.equal(opened.audio[0][0], mixed[0]);
  });

  it('drops a long noisy inhale instead of sending it with the vowel', () => {
    const state = createMicGateState();
    const onset = createOnsetQueue();
    const noise = fricative(0.12).subarray(0, wire);
    assert.equal(gateLiveFrame(noise, false, state, onset).silenceSamples, 0);
    assert.equal(gateLiveFrame(noise, false, state, onset).silenceSamples, 0);
    assert.equal(onset.frames.length, 2);
    const third = gateLiveFrame(noise, false, state, onset);
    assert.equal(third.audio.length, 0);
    assert.equal(third.silenceSamples, wire * 3);
    assert.equal(onset.breath, true);
    const voice = gateLiveFrame(vowel(0.06).subarray(0, wire), false, state, onset);
    assert.equal(voice.audio.length, 1);
    assert.equal(onset.breath, false);
  });

  it('forgets a held consonant when she starts talking, and still barges', () => {
    const state = createMicGateState();
    const onset = createOnsetQueue();
    gateLiveFrame(fricative(0.12).subarray(0, wire), false, state, onset);
    assert.equal(onset.frames.length, 1);
    const bleed = vowel(0.05).subarray(0, wire);
    const first = gateLiveFrame(bleed, true, state, onset);
    assert.equal(first.audio.length, 0);
    assert.equal(first.silenceSamples, 0);
    assert.equal(onset.frames.length, 0);
    gateLiveFrame(bleed, true, state, onset);
    const barge = gateLiveFrame(vowel(0.28).subarray(0, wire), true, state, onset);
    assert.equal(barge.barge, true);
    assert.equal(barge.audio.length, 1);
  });

  it('sends the start of a cross-frame barge and strips her bleed from it', () => {
    const state = createMicGateState();
    const onset = createOnsetQueue();
    const bleed = vowel(0.05).subarray(0, wire);
    gateLiveFrame(bleed, true, state, onset);
    gateLiveFrame(bleed, true, state, onset);
    const user = vowel(0.28);
    const tail = new Float32Array(wire);
    const head = new Float32Array(wire);
    tail.set(user.subarray(0, wire / 2), wire / 2);
    head.set(user.subarray(0, wire / 2), 0);
    const held = gateLiveFrame(tail, true, state, onset);
    assert.equal(held.audio.length, 0);
    const barge = gateLiveFrame(head, true, state, onset);
    assert.equal(barge.barge, true);
    assert.equal(barge.audio.length, 2);
    assert.equal(frameRms(barge.audio[0].subarray(0, wire / 2)), 0);
    assert.ok(frameRms(barge.audio[0].subarray(wire / 2)) > 0.05);
    assert.ok(frameRms(barge.audio[1].subarray(0, wire / 2)) > 0.05);
    assert.equal(frameRms(barge.audio[1].subarray(wire / 2)), 0);
  });

  it('strips her voice from the front of the barge frame', () => {
    const state = createMicGateState();
    const onset = createOnsetQueue();
    const bleed = vowel(0.05).subarray(0, wire);
    gateLiveFrame(bleed, true, state, onset);
    gateLiveFrame(bleed, true, state, onset);
    const frame = new Float32Array(wire);
    frame.set(bleed.subarray(0, 512));
    frame.set(vowel(0.28).subarray(0, wire - 512), 512);
    const barge = gateLiveFrame(frame, true, state, onset);
    assert.equal(barge.barge, true);
    assert.ok(frameRms(frame.subarray(0, 512)) > 0);
    assert.equal(frameRms(barge.audio[0].subarray(0, 512)), 0);
    assert.ok(frameRms(barge.audio[0].subarray(512)) > 0.05);
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

describe('chunkLivePcm', () => {
  it('splits a gate frame into 32 ms Live chunks', () => {
    assert.equal(LIVE_PCM_SAMPLES, 512);
    const pcm = new Int16Array(2048);
    for (let i = 0; i < pcm.length; i++) pcm[i] = i;
    const chunks = chunkLivePcm(pcm);
    assert.equal(chunks.length, 4);
    assert.ok(chunks.every((chunk) => chunk.length === 512));
    assert.equal(chunks[0][0], 0);
    assert.equal(chunks[3][511], 2047);
    assert.equal(chunkLivePcm(new Int16Array(0)).length, 0);
  });
});
