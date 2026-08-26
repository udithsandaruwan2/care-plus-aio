import { describe, expect, it } from 'vitest';
import { useAssistant } from './store';
import {
  applyCareRequestBookingState,
  promoteQueuedCareRequest,
} from './bookingFromCareRequest';
import type { CareRequest } from '@care-plus/api-client';

describe('bookingFromCareRequest', () => {
  it('sets awaiting_accept when a request is created online', () => {
    useAssistant.getState().reset();
    applyCareRequestBookingState({ caregiverId: 7, careRequestId: 99, queued: false });
    const s = useAssistant.getState();
    expect(s.focusedCaregiverId).toBe(7);
    expect(s.careRequestId).toBe(99);
    expect(s.bookingStage).toBe('awaiting_accept');
    expect(s.sessionLive).toBe(true);
  });

  it('keeps requested stage when queued offline', () => {
    useAssistant.getState().reset();
    applyCareRequestBookingState({ caregiverId: 7, queued: true });
    const s = useAssistant.getState();
    expect(s.bookingStage).toBe('requested');
    expect(s.careRequestId).toBeNull();
  });

  it('promotes queued request after flush', () => {
    useAssistant.getState().reset();
    useAssistant.setState({ bookingStage: 'requested' });
    promoteQueuedCareRequest({
      id: 55,
      caregiver_id: 3,
      caregiver_name: 'Asha',
      status: 'pending',
      patient_email: 'p@example.com',
      expires_at: new Date().toISOString(),
    } as CareRequest);
    const s = useAssistant.getState();
    expect(s.bookingStage).toBe('awaiting_accept');
    expect(s.careRequestId).toBe(55);
    expect(s.focusedCaregiverId).toBe(3);
  });
});
