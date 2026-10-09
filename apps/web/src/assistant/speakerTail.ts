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
