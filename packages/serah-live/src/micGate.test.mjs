import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { MIC_GATE, decideMicFrame, frameRms } from '../.test-out/micGate.js';

describe('decideMicFrame', () => {
  it('drops an inhale while nobody is speaking', () => {
    assert.equal(decideMicFrame(0.008, false), 'drop');
  });

  it('sends speech above the breath floor', () => {
    assert.equal(decideMicFrame(MIC_GATE.breathRms, false), 'send');
  });

  it('drops speaker bleed and breath while the assistant is talking', () => {
    assert.equal(decideMicFrame(0.04, true), 'drop');
  });

  it('treats a loud near-field frame as barge-in', () => {
    assert.equal(decideMicFrame(MIC_GATE.bargeRms, true), 'barge');
  });
});

describe('frameRms', () => {
  it('is zero for silence and about 0.5 for a half-scale square', () => {
    assert.equal(frameRms([0, 0, 0]), 0);
    const rms = frameRms([0.5, -0.5, 0.5, -0.5]);
    assert.ok(Math.abs(rms - 0.5) < 1e-9);
  });
});
