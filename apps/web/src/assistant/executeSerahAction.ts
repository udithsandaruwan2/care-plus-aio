import type { SerahAction } from '@care-plus/api-client';
import { useAssistant } from './store';
import { resolveCaregiverFromAction } from './resolveCaregiver';
import { checkCareRequestStatus } from './careRequestStatus';
import { confirmCheckoutFromVoice, selectPackageFromAction } from './voiceCheckout';

export type ExecuteSerahActionResult =
  | {
      ok: true;
      type: string;
      caregiverId?: number;
      queued?: boolean;
      careRequestId?: number;
      orderId?: number;
      needsOtp?: boolean;
    }
  | { ok: false; type: string; error: string };

/**
 * Run a structured Serah voice action against local match / checkout state.
 * ``request`` uses the same ``enqueueCareRequest`` path as MatchResultCards.
 * ``view_profile`` / ``describe_caregiver`` open the Serah profile drawer + TTS.
 * ``select_package`` / ``confirm_checkout`` drive voice checkout (Pay stays manual).
 */
export async function executeSerahAction(
  action: SerahAction | null | undefined,
): Promise<ExecuteSerahActionResult | null> {
  if (!action?.type) return null;

  const store = useAssistant.getState();
  const results = store.match?.results || [];
  const hit = resolveCaregiverFromAction(results, action);

  if (action.type === 'view_profile' || action.type === 'describe_caregiver') {
    if (hit) {
      store.setFocusedCaregiverId(hit.caregiver_id);
      store.setBookingStage('profile');
      store.setProfileNarrateMode(
        action.type === 'describe_caregiver' ? 'detail' : 'brief',
      );
      return { ok: true, type: action.type, caregiverId: hit.caregiver_id };
    }
    return { ok: false, type: action.type, error: 'No matching caregiver in the current list.' };
  }

  if (action.type === 'request') {
    if (!hit) {
      const error = 'I couldn’t tell which caregiver to request. Say a name or number from the list.';
      store.appendChat({ role: 'serah', text: error, route: 'ACTION' });
      return { ok: false, type: 'request', error };
    }
    try {
      const { enqueueCareRequest } = await import('../lib/outbox/flush');
      const outcome = await enqueueCareRequest(
        {
          caregiver_id: hit.caregiver_id,
          match_run_id: store.match?.request_id,
          match_snapshot: {
            rank: hit.rank,
            score: hit.score,
            breakdown: hit.breakdown,
            explanation: hit.explanation,
            distance_m: hit.distance_m ?? null,
          },
        },
        `Request to ${hit.display_name || 'caregiver'}`,
      );
      store.setFocusedCaregiverId(hit.caregiver_id);
      if (outcome.queued) {
        store.setBookingStage('requested');
        const queued =
          `Request to ${hit.display_name || 'this caregiver'} is queued and will send when you reconnect.`;
        const last = [...store.chat].reverse().find((m) => m.role === 'serah');
        if (last?.text !== queued) {
          store.appendChat({ role: 'serah', text: queued, route: 'ACTION' });
        }
        return {
          ok: true,
          type: 'request',
          caregiverId: hit.caregiver_id,
          queued: true,
        };
      }
      const createdId = outcome.result?.id;
      if (typeof createdId === 'number') {
        store.setCareRequestId(createdId);
      }
      store.setBookingStage('awaiting_accept');
      return {
        ok: true,
        type: 'request',
        caregiverId: hit.caregiver_id,
        queued: false,
        careRequestId: typeof createdId === 'number' ? createdId : undefined,
      };
    } catch (err) {
      const error =
        err instanceof Error ? err.message : 'Could not send the care request. Try again.';
      store.appendChat({ role: 'serah', text: error, route: 'ACTION' });
      return { ok: false, type: 'request', error };
    }
  }

  if (action.type === 'request_status') {
    const outcome = await checkCareRequestStatus({ speakIfPending: true });
    if (outcome === 'error') {
      return { ok: false, type: 'request_status', error: 'Status check failed.' };
    }
    return { ok: true, type: 'request_status' };
  }

  if (action.type === 'select_package') {
    const outcome = await selectPackageFromAction(action);
    if (!outcome.ok) {
      return { ok: false, type: 'select_package', error: outcome.error };
    }
    return { ok: true, type: 'select_package' };
  }

  if (action.type === 'confirm_checkout') {
    const outcome = await confirmCheckoutFromVoice();
    if (!outcome.ok) {
      return { ok: false, type: 'confirm_checkout', error: outcome.error };
    }
    if ('needsOtp' in outcome && outcome.needsOtp) {
      return { ok: true, type: 'confirm_checkout', needsOtp: true };
    }
    return {
      ok: true,
      type: 'confirm_checkout',
      orderId: 'orderId' in outcome ? outcome.orderId : undefined,
    };
  }

  if (action.type === 'cancel_flow') {
    return cancelBookingFlow();
  }

  return { ok: true, type: action.type, caregiverId: hit?.caregiver_id };
}

/** Cancel a pending care request (if any) and reset drawer / booking stage. */
async function cancelBookingFlow(): Promise<ExecuteSerahActionResult> {
  const store = useAssistant.getState();
  const careRequestId = store.careRequestId;
  const stage = store.bookingStage;
  let cancelledRequest = false;

  if (
    careRequestId != null &&
    (stage === 'awaiting_accept' || stage === 'requested')
  ) {
    try {
      const { api } = await import('../auth/api');
      await api.cancelCareRequest(careRequestId);
      cancelledRequest = true;
    } catch (err) {
      const error =
        err instanceof Error ? err.message : 'Could not cancel the care request.';
      store.appendChat({ role: 'serah', text: error, route: 'ACTION' });
      return { ok: false, type: 'cancel_flow', error };
    }
  }

  store.setFocusedCaregiverId(null);
  store.setCareRequestId(null);
  store.setBookingStage('idle');
  store.resetCheckoutDraft();
  store.clearProfileNarrate();

  const line = cancelledRequest
    ? 'Okay — I’ve cancelled that care request. Your match list is still here if you want someone else.'
    : 'Okay — I’ve closed that booking step. Your match list is still here if you want someone else.';
  const last = [...store.chat].reverse().find((m) => m.role === 'serah');
  if (last?.text !== line) {
    store.appendChat({ role: 'serah', text: line, route: 'ACTION' });
  }

  return {
    ok: true,
    type: 'cancel_flow',
    careRequestId: cancelledRequest ? careRequestId ?? undefined : undefined,
  };
}
