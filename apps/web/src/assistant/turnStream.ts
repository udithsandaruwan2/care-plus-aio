/** Tracks which voice-turn stages already applied via ``ws/match/`` (Step 83). */

export type TurnStage =
  | 'transcript'
  | 'intent'
  | 'route'
  | 'reply_text'
  | 'match'
  | 'reply_audio'
  | 'action'
  | 'done';

const STAGES = new Set<TurnStage>();
let activeRequestId = '';
let replySpoken = false;
let lastStreamedReply = '';

function normReply(text: string): string {
  return text.trim().replace(/\s+/g, ' ');
}

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

/**
 * HTTP path: apply a stage only once. Claims the stage so a late WS frame
 * cannot append/speak the same reply again.
 */
export function takeHttpTurnStage(stage: TurnStage, requestId?: string): boolean {
  if (!httpNeedsTurnStage(stage, requestId)) return false;
  return claimTurnStage(stage, requestId);
}

export function markTurnReplySpoken(text: string): void {
  replySpoken = true;
  lastStreamedReply = normReply(text);
}

export function turnReplyAlreadySpoken(text?: string): boolean {
  if (!replySpoken) return false;
  if (!text?.trim()) return true;
  return lastStreamedReply === normReply(text);
}

export function rememberStreamedReply(text: string): void {
  lastStreamedReply = normReply(text);
}

export function lastStreamedReplyText(): string {
  return lastStreamedReply;
}

/** True when this reply text was already appended for the active turn. */
export function replyTextAlreadyStreamed(text?: string): boolean {
  if (!text?.trim()) return false;
  return lastStreamedReply === normReply(text);
}
