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
 * After a gap, start a little in the future so a burst can play without a click between packets.
 */
export function schedulePcmStart(
  now: number,
  queuedUntil: number,
  preroll = PLAYBACK_PREROLL_SEC,
): number {
  if (queuedUntil > now) return queuedUntil;
  return now + preroll;
}
