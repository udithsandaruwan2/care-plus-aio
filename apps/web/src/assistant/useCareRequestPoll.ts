import { useEffect, useRef } from 'react';
import { useAssistant } from './store';
import { checkCareRequestStatus } from './careRequestStatus';

const POLL_MS = 5000;

/**
 * While the voice session is live and a care request is awaiting accept,
 * poll GET /care-requests/ about every 5s and advance the booking funnel.
 */
export function useCareRequestPoll(): void {
  const sessionLive = useAssistant((s) => s.sessionLive);
  const bookingStage = useAssistant((s) => s.bookingStage);
  const careRequestId = useAssistant((s) => s.careRequestId);
  const inFlight = useRef(false);

  useEffect(() => {
    if (!sessionLive || bookingStage !== 'awaiting_accept' || careRequestId == null) {
      return;
    }

    let cancelled = false;

    const tick = async () => {
      if (cancelled || inFlight.current) return;
      inFlight.current = true;
      try {
        await checkCareRequestStatus();
      } finally {
        inFlight.current = false;
      }
    };

    void tick();
    const timer = window.setInterval(() => {
      void tick();
    }, POLL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [sessionLive, bookingStage, careRequestId]);
}
