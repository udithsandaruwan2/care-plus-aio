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
 * Samples per playback pull. Must stay shorter than the preroll at 24 kHz,
 * or the first quantum is treated as an underrun and the opening syllable fades out.
 */
export const PLAYBACK_QUANTUM = 512;

/** If no sample has played by now, the graph is stuck and must not keep the mic closed. */
export const PLAYBACK_STALL_MS = 1000;

export type PlaybackHeard = { heard: number; lastPlayed: number; afterGap: boolean };

export function createPlaybackHeard(): PlaybackHeard {
  return { heard: 0, lastPlayed: 0, afterGap: false };
}

/**
 * An empty pull is a gap, not proof that this reply never played.
 * `afterGap` fades the next chunk back in without clearing what was already heard.
 */
export function notePlaybackPull(state: PlaybackHeard, played: number, held: boolean): PlaybackHeard {
  if (held) return state;
  if (played > 0) return { heard: state.heard + played, lastPlayed: played, afterGap: false };
  if (state.lastPlayed > 0) return { heard: state.heard, lastPlayed: state.lastPlayed, afterGap: true };
  return state;
}

/** How long her voice can still be in the room after the speakers stop. */
export const ECHO_TAIL_MS = 450;

/**
 * A barge cuts her playback, but the mic stays in the echo tail.
 * Her ring is not sent; the next nearer frame still takes the floor.
 */
export function micAfterBarge(now: number): {
  userHasFloor: false;
  turnOpen: false;
  echoTailUntil: number;
} {
  return { userHasFloor: false, turnOpen: false, echoTailUntil: now + ECHO_TAIL_MS };
}

/** What the mic should do when playback reports that she stopped. */
export function micAfterPlaybackStop(opts: {
  userHasFloor: boolean;
  turnOpen: boolean;
  audible: boolean;
}): 'floor' | 'gap' | 'tail' | 'open' {
  if (opts.userHasFloor) return 'floor';
  if (opts.audible && opts.turnOpen) return 'gap';
  if (opts.audible) return 'tail';
  return 'open';
}

export function playbackStalled(
  playedSamples: number,
  announced: boolean,
  elapsedMs: number,
  limitMs = PLAYBACK_STALL_MS,
): boolean {
  return announced && playedSamples === 0 && elapsedMs >= limitMs;
}

export function prerollCoversQuantum(
  sampleRate: number,
  quantum = PLAYBACK_QUANTUM,
  prerollSec = PLAYBACK_PREROLL_SEC,
): boolean {
  return Math.round(sampleRate * prerollSec) >= quantum;
}

export function appendPlayback(pending: Float32Array, incoming: ArrayLike<number>): Float32Array {
  const out = new Float32Array(pending.length + incoming.length);
  out.set(pending, 0);
  for (let i = 0; i < incoming.length; i++) out[pending.length + i] = incoming[i] ?? 0;
  return out;
}

/**
 * One continuous pull. Separate clips per chunk click at the join.
 * Before the preroll is primed, the frame stays silent.
 * A resume after silence fades in, and a frame that runs dry fades out,
 * so an underrun does not click.
 */
export function pullPlayback(
  pending: Float32Array,
  frameCount: number,
  primed: boolean,
  edge = 0,
  fromSilence = false,
  holdShort = false,
): { pending: Float32Array; output: Float32Array; played: number } {
  const output = new Float32Array(Math.max(0, frameCount));
  if (!primed || frameCount <= 0 || pending.length === 0) {
    return { pending, output, played: 0 };
  }
  // A short first quantum is not the end of the reply. Keep it until the next
  // pull so the opening is not faded away.
  if (holdShort && pending.length < frameCount) {
    return { pending, output, played: 0 };
  }
  const played = Math.min(frameCount, pending.length);
  output.set(pending.subarray(0, played));
  if (edge > 1) {
    if (fromSilence) {
      const n = Math.min(edge, played);
      for (let i = 0; i < n; i++) output[i] *= i / (n - 1);
    }
    if (played < frameCount) {
      const n = Math.min(edge, played);
      for (let i = 0; i < n; i++) output[played - 1 - i] *= i / (n - 1);
    }
  }
  return { pending: pending.subarray(played), output, played };
}

/** Rise out of silence so the first samples of a reply do not click. */
export function fadeInFromSilence(
  samples: Float32Array,
  sampleRate: number,
  seconds = 0.005,
): void {
  const n = Math.min(samples.length, Math.max(0, Math.round(sampleRate * seconds)));
  if (n <= 1) return;
  for (let i = 0; i < n; i++) samples[i] *= i / (n - 1);
}

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

/**
 * A missing chunk is not the end of her reply. Keep the mic closed until the
 * model marks the turn complete, or until this long with no further audio.
 */
export const TURN_IDLE_MS = 800;

/**
 * Mic mode while a reply may still be sounding.
 * `true` means she still owns the mic, so her own voice is not sent back.
 */
export function replyMicMode(
  userHasFloor: boolean,
  playbackActive: boolean,
  turnOpen: boolean,
  now: number,
  echoTailUntil: number,
): boolean | 'echo-tail' {
  if (userHasFloor) return false;
  if (playbackActive || turnOpen) return true;
  if (now < echoTailUntil) return 'echo-tail';
  return false;
}

/** Returns true once the idle grace has passed and stop should be announced. */
export function pollSpeakingStopped(watch: SpeakWatch, now: number, graceMs = 150): boolean {
  if (!watch.announced || watch.sources > 0 || watch.idleSince == null) return false;
  if (now - watch.idleSince < graceMs) return false;
  watch.announced = false;
  watch.idleSince = null;
  return true;
}
