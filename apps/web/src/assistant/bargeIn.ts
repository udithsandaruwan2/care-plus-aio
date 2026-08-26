/**
 * Near-field barge-in: interrupt Serah only when mic energy is both loud and
 * clearly above the ambient floor (far room voices should not stop her).
 */

export type BargeInConfig = {
  /** Live 0–1 mic level (analyser). */
  getAmplitude: () => number;
  /** Called once when barge-in fires. */
  onBargeIn: () => void;
  /** Ignore energy for this long after watch starts (speaker bleed). */
  graceMs?: number;
  /** Absolute peak amplitude required. */
  threshold?: number;
  /** Minimum amp − noiseFloor to treat as near speech. */
  floorDelta?: number;
  /** How long amplitude must stay above both gates. */
  sustainMs?: number;
  /** Optional clock (tests). */
  now?: () => number;
  /** Optional RAF (tests). */
  schedule?: (cb: () => void) => number;
  cancel?: (id: number) => void;
};

export const BARGE_IN_DEFAULTS = {
  graceMs: 700,
  threshold: 0.62,
  floorDelta: 0.28,
  sustainMs: 220,
} as const;

/**
 * Start watching. Returns a stop function.
 * Fires ``onBargeIn`` at most once when near-field energy sustains after grace.
 */
export function startBargeInWatch(config: BargeInConfig): () => void {
  const graceMs = config.graceMs ?? BARGE_IN_DEFAULTS.graceMs;
  const threshold = config.threshold ?? BARGE_IN_DEFAULTS.threshold;
  const floorDelta = config.floorDelta ?? BARGE_IN_DEFAULTS.floorDelta;
  const sustainMs = config.sustainMs ?? BARGE_IN_DEFAULTS.sustainMs;
  const now = config.now ?? (() => performance.now());
  const schedule = config.schedule ?? ((cb) => requestAnimationFrame(() => cb()));
  const cancel = config.cancel ?? ((id) => cancelAnimationFrame(id));

  const startedAt = now();
  let noiseFloor = 0.05;
  let floorReady = false;
  let aboveSince: number | null = null;
  let stopped = false;
  let rafId = 0;
  let fired = false;

  const tick = () => {
    if (stopped || fired) return;
    const t = now();
    const amp = config.getAmplitude();

    if (t - startedAt < graceMs) {
      // Seed floor from post-start bleed so we know the room baseline.
      noiseFloor = noiseFloor * 0.85 + amp * 0.15;
      aboveSince = null;
      rafId = schedule(tick);
      return;
    }

    if (!floorReady) {
      floorReady = true;
    }

    // Track quiet ambient; rise slowly so a near spike does not inflate the floor.
    if (amp < noiseFloor) {
      noiseFloor = noiseFloor * 0.6 + amp * 0.4;
    } else {
      noiseFloor = noiseFloor * 0.98 + amp * 0.02;
    }

    const near =
      amp >= threshold && amp >= noiseFloor + floorDelta;

    if (near) {
      if (aboveSince == null) aboveSince = t;
      else if (t - aboveSince >= sustainMs) {
        fired = true;
        config.onBargeIn();
        return;
      }
    } else {
      aboveSince = null;
    }
    rafId = schedule(tick);
  };

  rafId = schedule(tick);

  return () => {
    stopped = true;
    if (rafId) cancel(rafId);
    rafId = 0;
  };
}

/** Pure check used by unit tests for the near-field sustain math. */
export function bargeInShouldFire(opts: {
  elapsedMs: number;
  amplitude: number;
  aboveForMs: number;
  noiseFloor?: number;
  graceMs?: number;
  threshold?: number;
  floorDelta?: number;
  sustainMs?: number;
}): boolean {
  const graceMs = opts.graceMs ?? BARGE_IN_DEFAULTS.graceMs;
  const threshold = opts.threshold ?? BARGE_IN_DEFAULTS.threshold;
  const floorDelta = opts.floorDelta ?? BARGE_IN_DEFAULTS.floorDelta;
  const sustainMs = opts.sustainMs ?? BARGE_IN_DEFAULTS.sustainMs;
  const noiseFloor = opts.noiseFloor ?? 0;
  if (opts.elapsedMs < graceMs) return false;
  if (opts.amplitude < threshold) return false;
  if (opts.amplitude < noiseFloor + floorDelta) return false;
  return opts.aboveForMs >= sustainMs;
}
