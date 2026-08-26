import type { SerahAction } from '@care-plus/api-client';
import { useAssistant } from './store';
import { resolveCaregiverFromAction } from './resolveCaregiver';

export type ExecuteSerahActionResult =
  | { ok: true; type: string; caregiverId?: number; queued?: boolean }
  | { ok: false; type: string; error: string };

/**
 * Run a structured Serah voice action against local match state.
 * ``request`` uses the same ``enqueueCareRequest`` path as MatchResultCards.
 * ``view_profile`` / ``describe_caregiver`` open the Serah profile drawer + TTS.
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
      store.setBookingStage('requested');
      if (outcome.queued) {
        const queued =
          `Request to ${hit.display_name || 'this caregiver'} is queued and will send when you reconnect.`;
        const last = [...store.chat].reverse().find((m) => m.role === 'serah');
        if (last?.text !== queued) {
          store.appendChat({ role: 'serah', text: queued, route: 'ACTION' });
        }
      }
      return {
        ok: true,
        type: 'request',
        caregiverId: hit.caregiver_id,
        queued: Boolean(outcome.queued),
      };
    } catch (err) {
      const error =
        err instanceof Error ? err.message : 'Could not send the care request. Try again.';
      store.appendChat({ role: 'serah', text: error, route: 'ACTION' });
      return { ok: false, type: 'request', error };
    }
  }

  // Later slices: request_status, select_package, confirm_checkout, cancel_flow.
  return { ok: true, type: action.type, caregiverId: hit?.caregiver_id };
}
