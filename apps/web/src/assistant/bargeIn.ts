/**
 * Barge-in: watch mic energy during Serah playback and interrupt when the user speaks.
 * Echo guard = startup grace + high threshold + sustained window (Step 85).
 */

export type BargeInConfig = {
  /** Live 0–1 mic level (analyser). */
  getAmplitude: () => number;
  /** Called once when barge-in fires. */
  onBargeIn: () => void;
  /** Ignore energy for this long after watch starts (speaker bleed). Default 450ms. */
  graceMs?: number;
  /** Peak amplitude required. Default 0.48 (above typical speaker echo). */
  threshold?: number;
  /** How long amplitude must stay above threshold. Default 100ms. */
  sustainMs?: number;
  /** Optional clock (tests). */
  now?: () => number;
  /** Optional RAF (tests). */
  schedule?: (cb: () => void) => number;
  cancel?: (id: number) => void;
};

export const BARGE_IN_DEFAULTS = {
  graceMs: 450,
  threshold: 0.48,
  sustainMs: 100,
} as const;

/**
 * Start watching. Returns a stop function.
 * Fires ``onBargeIn`` at most once when energy stays above threshold after the grace period.
 */
export function startBargeInWatch(config: BargeInConfig): () => void {
  const graceMs = config.graceMs ?? BARGE_IN_DEFAULTS.graceMs;
  const threshold = config.threshold ?? BARGE_IN_DEFAULTS.threshold;
  const sustainMs = config.sustainMs ?? BARGE_IN_DEFAULTS.sustainMs;
  const now = config.now ?? (() => performance.now());
  const schedule = config.schedule ?? ((cb) => requestAnimationFrame(() => cb()));
  const cancel = config.cancel ?? ((id) => cancelAnimationFrame(id));

  const startedAt = now();
  let aboveSince: number | null = null;
  let stopped = false;
  let rafId = 0;
  let fired = false;

  const tick = () => {
    if (stopped || fired) return;
    const t = now();
    if (t - startedAt < graceMs) {
      aboveSince = null;
      rafId = schedule(tick);
      return;
    }
    const amp = config.getAmplitude();
    if (amp >= threshold) {
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

/** Pure check used by unit tests for the sustain window math. */
export function bargeInShouldFire(opts: {
  elapsedMs: number;
  amplitude: number;
  aboveForMs: number;
  graceMs?: number;
  threshold?: number;
  sustainMs?: number;
}): boolean {
  const graceMs = opts.graceMs ?? BARGE_IN_DEFAULTS.graceMs;
  const threshold = opts.threshold ?? BARGE_IN_DEFAULTS.threshold;
  const sustainMs = opts.sustainMs ?? BARGE_IN_DEFAULTS.sustainMs;
  if (opts.elapsedMs < graceMs) return false;
  if (opts.amplitude < threshold) return false;
  return opts.aboveForMs >= sustainMs;
}
