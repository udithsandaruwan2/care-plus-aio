import type { CareRequest, MatchHit } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAssistant } from './store';
import { speakSerah, stopSpeaking } from './useTts';

/** Next VEHMF hit after the caregiver who just rejected (by rank). */
export function nextRankedCaregiver(
  results: MatchHit[] | null | undefined,
  currentCaregiverId: number | null | undefined,
): MatchHit | null {
  const rows = [...(results || [])].sort((a, b) => a.rank - b.rank);
  if (!rows.length) return null;
  if (currentCaregiverId == null) return rows[1] ?? null;
  const idx = rows.findIndex((r) => r.caregiver_id === currentCaregiverId);
  if (idx < 0) return rows[0] ?? null;
  return rows[idx + 1] ?? null;
}

export function acceptedNarration(name: string): string {
  return (
    `${name} accepted your care request. ` +
    `I’ll list a few care packages next so we can checkout by voice. ` +
    `You can also open Messages anytime to say hi.`
  );
}

export function rejectedWithNextNarration(declinedName: string, next: MatchHit): string {
  const nextName = next.display_name || 'the next caregiver';
  return (
    `${declinedName} declined. ` +
    `Next on the list is ${nextName}, number ${next.rank}. ` +
    `Want me to send them a request?`
  );
}

export function rejectedNoNextNarration(declinedName: string): string {
  return (
    `${declinedName} declined, and there are no more matches in this list. ` +
    `Say find caregivers if you want a fresh search.`
  );
}

export function pendingNarration(name: string): string {
  return `Still waiting on ${name}. I’ll keep checking and let you know when they respond.`;
}

export function unknownStatusNarration(): string {
  return `I don’t see an active care request yet. Say send the request after we pick someone.`;
}

function announce(text: string): void {
  if (!text.trim()) return;
  const store = useAssistant.getState();
  const last = [...store.chat].reverse().find((m) => m.role === 'serah');
  if (last?.text.trim() === text.trim()) return;
  stopSpeaking();
  store.appendChat({ role: 'serah', text, route: 'ACTION' });
  void speakSerah(text, store.uiLanguage);
}

/**
 * Apply a terminal care-request status to the booking funnel.
 * Returns true when the poll should stop (accepted / rejected / cancelled / expired).
 */
export function applyCareRequestTerminalStatus(row: CareRequest): boolean {
  const store = useAssistant.getState();
  const name = row.caregiver_name || 'That caregiver';

  if (row.status === 'accepted') {
    store.setBookingStage('packages');
    store.resetCheckoutDraft();
    announce(acceptedNarration(name));
    void import('./voiceCheckout').then((m) => m.offerPackagesAfterAccept());
    return true;
  }

  if (row.status === 'rejected') {
    const next = nextRankedCaregiver(store.match?.results, row.caregiver_id);
    store.setCareRequestId(null);
    if (next) {
      store.setFocusedCaregiverId(next.caregiver_id);
      store.setBookingStage('profile');
      announce(rejectedWithNextNarration(name, next));
    } else {
      store.setBookingStage('idle');
      announce(rejectedNoNextNarration(name));
    }
    return true;
  }

  if (row.status === 'cancelled' || row.status === 'expired') {
    store.setCareRequestId(null);
    store.setBookingStage('idle');
    announce(
      row.status === 'cancelled'
        ? `That care request was cancelled.`
        : `That care request expired. Say send the request to try again.`,
    );
    return true;
  }

  return false;
}

/** One-shot status check for voice ``request_status`` (and the poll loop). */
export async function checkCareRequestStatus(opts?: {
  /** Speak even when still pending (user asked "any update?"). */
  speakIfPending?: boolean;
}): Promise<'pending' | 'terminal' | 'missing' | 'error'> {
  const store = useAssistant.getState();
  const id = store.careRequestId;
  if (id == null) {
    if (opts?.speakIfPending) announce(unknownStatusNarration());
    return 'missing';
  }

  try {
    const list = await api.listCareRequests();
    const row = list.results.find((r) => r.id === id);
    if (!row) {
      if (opts?.speakIfPending) {
        announce(`I couldn’t find care request ${id} right now. Try again in a moment.`);
      }
      return 'missing';
    }

    if (applyCareRequestTerminalStatus(row)) return 'terminal';

    if (opts?.speakIfPending) {
      announce(pendingNarration(row.caregiver_name || 'the caregiver'));
    }
    return 'pending';
  } catch {
    if (opts?.speakIfPending) {
      announce(`I couldn’t check the request status just now. I’ll try again shortly.`);
    }
    return 'error';
  }
}
