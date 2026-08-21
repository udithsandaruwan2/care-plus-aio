/**
 * End-of-utterance watch: after voice energy is heard, stop when it stays quiet.
 * Complements Web Speech caption silence — catches cases where ambient noise
 * keeps the mic open after the user finishes speaking.
 */

export type EndOfUtteranceConfig = {
  getAmplitude: () => number;
  /** Called once when post-speech silence is detected. */
  onEnd: () => void;
  /** Ignore levels briefly after start (button click / mic open). Default 300ms. */
  graceMs?: number;
  /** Amplitude that counts as “started speaking”. Default 0.18. */
  speechThreshold?: number;
  /** How long speech must stay above threshold. Default 80ms. */
  speechSustainMs?: number;
  /** Amplitude below this counts as quiet. Default 0.1. */
  silenceThreshold?: number;
  /** How long to stay quiet after speech before ending. Default 900ms. */
  silenceMs?: number;
  now?: () => number;
  schedule?: (cb: () => void) => number;
  cancel?: (id: number) => void;
};

export const END_OF_UTTERANCE_DEFAULTS = {
  graceMs: 300,
  speechThreshold: 0.18,
  speechSustainMs: 80,
  silenceThreshold: 0.1,
  silenceMs: 900,
} as const;

/**
 * Start watching. Returns a stop function.
 * Fires ``onEnd`` at most once after speech-then-silence.
 */
export function startEndOfUtteranceWatch(config: EndOfUtteranceConfig): () => void {
  const graceMs = config.graceMs ?? END_OF_UTTERANCE_DEFAULTS.graceMs;
  const speechThreshold = config.speechThreshold ?? END_OF_UTTERANCE_DEFAULTS.speechThreshold;
  const speechSustainMs = config.speechSustainMs ?? END_OF_UTTERANCE_DEFAULTS.speechSustainMs;
  const silenceThreshold = config.silenceThreshold ?? END_OF_UTTERANCE_DEFAULTS.silenceThreshold;
  const silenceMs = config.silenceMs ?? END_OF_UTTERANCE_DEFAULTS.silenceMs;
  const now = config.now ?? (() => performance.now());
  const schedule = config.schedule ?? ((cb) => requestAnimationFrame(() => cb()));
  const cancel = config.cancel ?? ((id) => cancelAnimationFrame(id));

  const startedAt = now();
  let heardSpeech = false;
  let aboveSince: number | null = null;
  let belowSince: number | null = null;
  let stopped = false;
  let rafId = 0;
  let fired = false;

  const tick = () => {
    if (stopped || fired) return;
    const t = now();
    if (t - startedAt < graceMs) {
      aboveSince = null;
      belowSince = null;
      rafId = schedule(tick);
      return;
    }

    const amp = config.getAmplitude();

    if (!heardSpeech) {
      if (amp >= speechThreshold) {
        if (aboveSince == null) aboveSince = t;
        else if (t - aboveSince >= speechSustainMs) {
          heardSpeech = true;
          belowSince = null;
        }
      } else {
        aboveSince = null;
      }
      rafId = schedule(tick);
      return;
    }

    if (amp < silenceThreshold) {
      if (belowSince == null) belowSince = t;
      else if (t - belowSince >= silenceMs) {
        fired = true;
        config.onEnd();
        return;
      }
    } else {
      belowSince = null;
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

/** Pure helper for unit tests. */
export function endOfUtteranceShouldFire(opts: {
  heardSpeech: boolean;
  amplitude: number;
  belowForMs: number;
  silenceThreshold?: number;
  silenceMs?: number;
}): boolean {
  if (!opts.heardSpeech) return false;
  const silenceThreshold = opts.silenceThreshold ?? END_OF_UTTERANCE_DEFAULTS.silenceThreshold;
  const silenceMs = opts.silenceMs ?? END_OF_UTTERANCE_DEFAULTS.silenceMs;
  if (opts.amplitude >= silenceThreshold) return false;
  return opts.belowForMs >= silenceMs;
}
