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
