import { describe, expect, it, vi } from 'vitest';
import { bargeInShouldFire, BARGE_IN_DEFAULTS, startBargeInWatch } from './bargeIn';

describe('bargeInShouldFire', () => {
  it('ignores energy during grace period (echo guard)', () => {
    expect(
      bargeInShouldFire({
        elapsedMs: 200,
        amplitude: 0.99,
        aboveForMs: 500,
        noiseFloor: 0.05,
      }),
    ).toBe(false);
  });

  it('ignores low amplitude after grace (empty room / speaker bleed)', () => {
    expect(
      bargeInShouldFire({
        elapsedMs: BARGE_IN_DEFAULTS.graceMs + 50,
        amplitude: 0.2,
        aboveForMs: 500,
        noiseFloor: 0.05,
      }),
    ).toBe(false);
  });

  it('rejects steady far-room energy that sits near the floor', () => {
    expect(
      bargeInShouldFire({
        elapsedMs: BARGE_IN_DEFAULTS.graceMs + 50,
        amplitude: 0.5,
        aboveForMs: 500,
        noiseFloor: 0.4,
      }),
    ).toBe(false);
  });

  it('fires when near speech clears absolute and floor-delta gates', () => {
    expect(
      bargeInShouldFire({
        elapsedMs: BARGE_IN_DEFAULTS.graceMs + 50,
        amplitude: BARGE_IN_DEFAULTS.threshold,
        aboveForMs: BARGE_IN_DEFAULTS.sustainMs,
        noiseFloor: 0.1,
      }),
    ).toBe(true);
  });
});

describe('startBargeInWatch', () => {
  it('does not fire on sustained mid-level noise after grace', () => {
    let t = 0;
    let amp = 0.35;
    const onBargeIn = vi.fn();
    const timers: Array<() => void> = [];

    const stop = startBargeInWatch({
      getAmplitude: () => amp,
      onBargeIn,
      graceMs: 50,
      sustainMs: 40,
      threshold: 0.62,
      floorDelta: 0.28,
      now: () => t,
      schedule: (cb) => {
        timers.push(cb);
        return timers.length;
      },
      cancel: () => undefined,
    });

    for (let i = 0; i < 8; i += 1) {
      t += 30;
      timers.shift()?.();
      // push next scheduled tick from previous call
      while (timers.length > 1) timers.shift();
    }
    expect(onBargeIn).not.toHaveBeenCalled();
    stop();
  });

  it('fires within sustain window of a near spike after grace', () => {
    let t = 0;
    let amp = 0.1;
    const onBargeIn = vi.fn();
    const timers: Array<() => void> = [];

    const stop = startBargeInWatch({
      getAmplitude: () => amp,
      onBargeIn,
      graceMs: 50,
      sustainMs: 40,
      threshold: 0.5,
      floorDelta: 0.2,
      now: () => t,
      schedule: (cb) => {
        timers.push(cb);
        return timers.length;
      },
      cancel: () => undefined,
    });

    // During grace — loud energy must not fire.
    amp = 0.9;
    t = 30;
    timers.shift()?.();
    expect(onBargeIn).not.toHaveBeenCalled();

    // After grace, quiet floor then near spike.
    amp = 0.12;
    t = 60;
    timers.shift()?.();
    amp = 0.85;
    t = 70;
    timers.shift()?.();
    t = 120;
    timers.shift()?.();
    expect(onBargeIn).toHaveBeenCalledTimes(1);

    stop();
  });
});
