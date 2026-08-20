import { ApiError, isNetworkError, isTimeoutError } from '@care-plus/api-client';

export type TurnFailureKind =
  | 'network'
  | 'timeout'
  | 'throttle'
  | 'consent'
  | 'auth'
  | 'unknown';

export type TurnFailure = {
  kind: TurnFailureKind;
  message: string;
  /** Network / timeout failures auto-replay once when connectivity returns. */
  autoReplay: boolean;
  canRetry: boolean;
};

export type PendingTurn = {
  text: string;
  audio: Blob | null;
};

const CONSENT_STATUS = 451;

export function classifyTurnFailure(err: unknown): TurnFailure {
  if (isTimeoutError(err)) {
    return {
      kind: 'timeout',
      message: 'That took too long — check your connection and try again.',
      autoReplay: true,
      canRetry: true,
    };
  }
  if (isNetworkError(err)) {
    return {
      kind: 'network',
      message: 'You appear offline — we kept what you said. Retry when you are back online.',
      autoReplay: true,
      canRetry: true,
    };
  }
  if (err instanceof ApiError) {
    if (err.status === CONSENT_STATUS) {
      return {
        kind: 'consent',
        message: 'AI processing needs your consent before we can understand your request.',
        autoReplay: false,
        canRetry: false,
      };
    }
    if (err.status === 401) {
      return {
        kind: 'auth',
        message: 'Session expired — sign in again, then tap the mic.',
        autoReplay: false,
        canRetry: false,
      };
    }
    if (err.status === 429) {
      return {
        kind: 'throttle',
        message: 'Serah is busy — wait a moment, then retry your message.',
        autoReplay: false,
        canRetry: true,
      };
    }
    return {
      kind: 'unknown',
      message: err.message || `Request failed (${err.status}).`,
      autoReplay: false,
      canRetry: true,
    };
  }
  return {
    kind: 'unknown',
    message: err instanceof Error ? err.message : 'Could not understand that. Try again.',
    autoReplay: false,
    canRetry: true,
  };
}
