import { describe, expect, it, vi } from 'vitest';
import { bargeInShouldFire, BARGE_IN_DEFAULTS, startBargeInWatch } from './bargeIn';

describe('bargeInShouldFire', () => {
  it('ignores energy during grace period (echo guard)', () => {
    expect(
      bargeInShouldFire({
        elapsedMs: 200,
        amplitude: 0.99,
        aboveForMs: 500,
      }),
    ).toBe(false);
  });

  it('ignores low amplitude after grace (empty room / speaker bleed)', () => {
    expect(
      bargeInShouldFire({
        elapsedMs: BARGE_IN_DEFAULTS.graceMs + 50,
        amplitude: 0.2,
        aboveForMs: 500,
      }),
    ).toBe(false);
  });

  it('fires when sustained speech energy crosses threshold', () => {
    expect(
      bargeInShouldFire({
        elapsedMs: BARGE_IN_DEFAULTS.graceMs + 50,
        amplitude: BARGE_IN_DEFAULTS.threshold,
        aboveForMs: BARGE_IN_DEFAULTS.sustainMs,
      }),
    ).toBe(true);
  });
});

describe('startBargeInWatch', () => {
  it('fires within ~300ms of sustained speech after grace', () => {
    let t = 0;
    let amp = 0;
    const onBargeIn = vi.fn();
    const timers: Array<() => void> = [];

    const stop = startBargeInWatch({
      getAmplitude: () => amp,
      onBargeIn,
      graceMs: 50,
      sustainMs: 40,
      threshold: 0.5,
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

    // After grace, sustain window.
    t = 60;
    timers.shift()?.();
    t = 100;
    timers.shift()?.();
    expect(onBargeIn).toHaveBeenCalledTimes(1);

    stop();
  });
});
