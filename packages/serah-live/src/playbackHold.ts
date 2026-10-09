/** After a barge-in, ignore leftover model audio until that turn ends. */

export type PlaybackHold = {
  holding: boolean;
};

export function createPlaybackHold(): PlaybackHold {
  return { holding: false };
}

export function holdPlayback(state: PlaybackHold): void {
  state.holding = true;
}

export function releasePlayback(state: PlaybackHold): void {
  state.holding = false;
}

export function shouldPlayPcm(state: PlaybackHold): boolean {
  return !state.holding;
}

/** Let the next reply through if the model never closes the interrupted turn. */
export const HOLD_LIMIT_MS = 2500;

export function holdReleaseDue(elapsedMs: number, limitMs = HOLD_LIMIT_MS): boolean {
  return elapsedMs >= limitMs;
}

/**
 * The model sends 24 kHz PCM. The device context is often 44.1 or 48 kHz, and
 * `createBuffer` rejects a buffer whose rate does not match the context.
 * Linear resampling keeps her pitch and duration at whatever rate the context is.
 */
export function resamplePlayback(
  samples: ArrayLike<number>,
  fromRate: number,
  toRate: number,
): Float32Array {
  const same = new Float32Array(samples.length);
  for (let i = 0; i < samples.length; i++) same[i] = samples[i] ?? 0;
  if (samples.length === 0 || fromRate <= 0 || toRate <= 0 || Math.abs(fromRate - toRate) < 1) {
    return same;
  }
  const outLen = Math.max(1, Math.round((samples.length * toRate) / fromRate));
  const out = new Float32Array(outLen);
  const scale = fromRate / toRate;
  const last = samples.length - 1;
  for (let i = 0; i < outLen; i++) {
    const pos = i * scale;
    const j = Math.min(last, Math.floor(pos));
    const frac = pos - j;
    const a = samples[j] ?? 0;
    const b = samples[Math.min(last, j + 1)] ?? a;
    out[i] = a + (b - a) * frac;
  }
  return out;
}

/** Seconds to wait after a gap so the next chunks can line up before sound starts. */
export const PLAYBACK_PREROLL_SEC = 0.08;

/**
 * Chain a chunk onto audio that is already queued.
 * The first chunk of a turn waits a short preroll so a burst can line up.
 * A late chunk mid-turn starts immediately, so each gap is not padded again.
 */
export function schedulePcmStart(
  now: number,
  queuedUntil: number,
  preroll = PLAYBACK_PREROLL_SEC,
): number {
  if (queuedUntil > now) return queuedUntil;
  if (queuedUntil <= 0) return now + preroll;
  return now;
}

export type SpeakWatch = {
  sources: number;
  /** Set when the last source ends. Cleared when a new source starts. */
  idleSince: number | null;
  announced: boolean;
};

export function createSpeakWatch(): SpeakWatch {
  return { sources: 0, idleSince: null, announced: false };
}

/** Returns true when playback should be announced as started. */
export function onSourceStart(watch: SpeakWatch): boolean {
  watch.sources += 1;
  watch.idleSince = null;
  if (watch.announced) return false;
  watch.announced = true;
  return true;
}

export function onSourceEnd(watch: SpeakWatch, now: number): void {
  watch.sources = Math.max(0, watch.sources - 1);
  if (watch.sources === 0) watch.idleSince = now;
}

/** Returns true once the idle grace has passed and stop should be announced. */
export function pollSpeakingStopped(watch: SpeakWatch, now: number, graceMs = 150): boolean {
  if (!watch.announced || watch.sources > 0 || watch.idleSince == null) return false;
  if (now - watch.idleSince < graceMs) return false;
  watch.announced = false;
  watch.idleSince = null;
  return true;
}
