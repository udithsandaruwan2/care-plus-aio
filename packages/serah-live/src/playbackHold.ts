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
