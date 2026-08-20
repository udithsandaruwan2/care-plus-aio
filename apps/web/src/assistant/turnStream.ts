/** Tracks which voice-turn stages already applied via ``ws/match/`` (Step 83). */

export type TurnStage =
  | 'transcript'
  | 'intent'
  | 'route'
  | 'reply_text'
  | 'match'
  | 'reply_audio'
  | 'done';

const STAGES = new Set<TurnStage>();
let activeRequestId = '';
let replySpoken = false;
let lastStreamedReply = '';

/** Call at the start of each ``voiceTurn`` HTTP request. */
export function resetTurnStream(): void {
  STAGES.clear();
  activeRequestId = '';
  replySpoken = false;
  lastStreamedReply = '';
}

function adoptRequestId(rid: string | undefined): void {
  const id = (rid || '').trim();
  if (!id) return;
  if (id !== activeRequestId) {
    activeRequestId = id;
    STAGES.clear();
    replySpoken = false;
    lastStreamedReply = '';
  }
}

/** Returns true when this stage should mutate the UI (first time for the turn). */
export function claimTurnStage(stage: TurnStage, requestId?: string): boolean {
  adoptRequestId(requestId);
  if (STAGES.has(stage)) return false;
  STAGES.add(stage);
  return true;
}

/** True when HTTP must still apply this stage (socket missed it or was down). */
export function httpNeedsTurnStage(stage: TurnStage, requestId?: string): boolean {
  const id = (requestId || '').trim();
  if (id && activeRequestId && id !== activeRequestId) {
    return true;
  }
  if (id && !activeRequestId) {
    activeRequestId = id;
  }
  return !STAGES.has(stage);
}

export function markTurnReplySpoken(text: string): void {
  replySpoken = true;
  lastStreamedReply = text.trim();
}

export function turnReplyAlreadySpoken(text?: string): boolean {
  if (!replySpoken) return false;
  if (!text?.trim()) return true;
  return lastStreamedReply === text.trim();
}

export function rememberStreamedReply(text: string): void {
  lastStreamedReply = text.trim();
}

export function lastStreamedReplyText(): string {
  return lastStreamedReply;
}
