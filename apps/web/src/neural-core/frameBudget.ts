import { AssistantState } from '@care-plus/core';

/** Idle / listening / thinking: cap the mesh loop near 30 fps. */
export const IDLE_FRAME_SEC = 1 / 30;

/** Speaking and emergency keep a 60 fps loop so the orb still reacts. */
export const LIVE_FRAME_SEC = 1 / 60;

/** Ignore mic jitter below this when deciding to rewrite instance matrices. */
export const AMP_EPS = 0.012;

/** Cap React publishes of mic amplitude (~15 Hz). */
export const AMP_PUBLISH_HZ = 15;

export function isHotNeuralState(state: AssistantState): boolean {
  return (
    state === AssistantState.SPEAKING ||
    state === AssistantState.CHAT_REPLY ||
    state === AssistantState.EMERGENCY
  );
}

export function frameIntervalSec(state: AssistantState): number {
  return isHotNeuralState(state) ? LIVE_FRAME_SEC : IDLE_FRAME_SEC;
}

/** True when the 104-neuron instance buffer must be rewritten this tick. */
export function neuronMatricesDirty(opts: {
  hot: boolean;
  ampDelta: number;
  stateChanged: boolean;
}): boolean {
  if (opts.hot || opts.stateChanged) return true;
  return opts.ampDelta >= AMP_EPS;
}

export function shouldPublishAmplitude(
  nowMs: number,
  lastMs: number,
  hz: number = AMP_PUBLISH_HZ,
): boolean {
  return nowMs - lastMs >= 1000 / hz;
}
