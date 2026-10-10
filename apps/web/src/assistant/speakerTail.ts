/** How long to leave the mic closed after Serah's speakers stop. */
export const SPEAKER_TAIL_MS = 450;

/** The fallback listener must not reopen onto her own speaker tail, or beside Live. */
export function shouldReopenMicAfterSpeech(opts: {
  conversationOn: boolean;
  busy: boolean;
  liveActive: boolean;
}): boolean {
  return opts.conversationOn && !opts.busy && !opts.liveActive;
}

/**
 * After a barge, Web Speech waits out her ring. Live already owns the mic.
 * `busy` does not block this: the user cut her off in order to speak.
 */
export function shouldListenAfterBarge(opts: {
  conversationOn: boolean;
  liveActive: boolean;
}): boolean {
  return opts.conversationOn && !opts.liveActive;
}

/** A real user utterance replaces the cut-off line. An empty barge may finish it. */
export function shouldPlayCutOffAfterBarge(userSpoke: boolean): boolean {
  return !userSpoke;
}

/**
 * The near-field barge mic listens to the room. It must not run beside Live,
 * or it hears her and opens a second turn.
 */
export function shouldArmFallbackBargeMic(liveActive: boolean): boolean {
  return !liveActive;
}

/** An empty caption may rearm Web Speech only when Live is not already listening. */
export function shouldRearmFallbackMic(opts: {
  conversationOn: boolean;
  busy: boolean;
  liveActive: boolean;
  ending: boolean;
}): boolean {
  return !opts.ending && shouldReopenMicAfterSpeech(opts);
}
