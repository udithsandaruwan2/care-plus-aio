/**
 * Whether a Gemini Live session is the voice in the room.
 * Browser and HTTP speech must stay quiet then, or the mic hears her twice.
 */

let open = false;

export function setLiveSessionOpen(next: boolean): void {
  open = next;
}

export function liveSessionOpen(): boolean {
  return open;
}

/** Fallback TTS is only for when Live is not already speaking. */
export function fallbackVoiceAllowed(): boolean {
  return !open;
}
