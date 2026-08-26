import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useCareRequestPoll } from './useCareRequestPoll';
import { useAssistant } from './store';

vi.mock('./careRequestStatus', () => ({
  checkCareRequestStatus: vi.fn(async () => 'pending'),
}));

import { checkCareRequestStatus } from './careRequestStatus';

describe('useCareRequestPoll', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useAssistant.getState().reset();
    vi.mocked(checkCareRequestStatus).mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('polls while awaiting_accept with a careRequestId and live session', async () => {
    useAssistant.setState({
      sessionLive: true,
      bookingStage: 'awaiting_accept',
      careRequestId: 42,
    });

    renderHook(() => useCareRequestPoll());

    await act(async () => {
      await Promise.resolve();
    });
    expect(checkCareRequestStatus).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(5000);
      await Promise.resolve();
    });
    expect(checkCareRequestStatus).toHaveBeenCalledTimes(2);
  });

  it('does not poll when booking stage is idle', async () => {
    useAssistant.setState({
      sessionLive: true,
      bookingStage: 'idle',
      careRequestId: 42,
    });
    renderHook(() => useCareRequestPoll());
    await act(async () => {
      await Promise.resolve();
    });
    expect(checkCareRequestStatus).not.toHaveBeenCalled();
  });
});
