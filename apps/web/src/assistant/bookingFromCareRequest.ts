import type { CareRequest } from '@care-plus/api-client';
import { useAssistant } from './store';

/**
 * Sync Serah booking funnel after a care request is created (voice or card tap).
 * Offline queue uses ``requested`` until flush promotes via ``promoteQueuedCareRequest``.
 */
export function applyCareRequestBookingState(opts: {
  caregiverId: number;
  careRequestId?: number | null;
  queued?: boolean;
}): void {
  const store = useAssistant.getState();
  store.setFocusedCaregiverId(opts.caregiverId);
  store.setSessionLive(true);
  if (opts.queued) {
    store.setCareRequestId(null);
    store.setBookingStage('requested');
    return;
  }
  if (typeof opts.careRequestId === 'number') {
    store.setCareRequestId(opts.careRequestId);
  }
  store.setBookingStage('awaiting_accept');
}

/** After outbox delivers a queued care_request, start accept polling. */
export function promoteQueuedCareRequest(row: CareRequest): void {
  const store = useAssistant.getState();
  if (store.bookingStage !== 'requested' && store.bookingStage !== 'idle') {
    // Don't clobber packages/pay if user already moved on.
    if (store.bookingStage === 'packages' || store.bookingStage === 'pay') return;
  }
  const caregiverId = row.caregiver_id;
  store.setFocusedCaregiverId(caregiverId);
  store.setCareRequestId(row.id);
  store.setBookingStage('awaiting_accept');
  store.setSessionLive(true);
  const name = row.caregiver_name || 'this caregiver';
  const line = `Request to ${name} was sent. I’ll watch for their response.`;
  const last = [...store.chat].reverse().find((m) => m.role === 'serah');
  if (last?.text.trim() !== line) {
    store.appendChat({ role: 'serah', text: line, route: 'ACTION' });
  }
}
