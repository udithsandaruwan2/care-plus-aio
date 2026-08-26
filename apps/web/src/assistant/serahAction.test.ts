import { describe, expect, it, beforeEach, vi } from 'vitest';
import {
  claimTurnStage,
  httpNeedsTurnStage,
  markTurnReplySpoken,
  rememberStreamedReply,
  replyTextAlreadyStreamed,
  resetTurnStream,
  takeHttpTurnStage,
  turnReplyAlreadySpoken,
} from './turnStream';

describe('turnStream HTTP+WS dedupe', () => {
  beforeEach(() => {
    resetTurnStream();
  });

  it('claims each stage once per request id', () => {
    expect(claimTurnStage('reply_text', 'r1')).toBe(true);
    expect(claimTurnStage('reply_text', 'r1')).toBe(false);
    expect(httpNeedsTurnStage('reply_text', 'r1')).toBe(false);
  });

  it('takeHttpTurnStage marks the stage so a late WS cannot re-apply', () => {
    expect(takeHttpTurnStage('reply_text', 'r2')).toBe(true);
    expect(takeHttpTurnStage('reply_text', 'r2')).toBe(false);
    expect(claimTurnStage('reply_text', 'r2')).toBe(false);
  });

  it('dedupes reply text by normalized hash', () => {
    rememberStreamedReply('  Hello   Serah  ');
    expect(replyTextAlreadyStreamed('Hello Serah')).toBe(true);
    expect(replyTextAlreadyStreamed('Hello Serah!')).toBe(false);
  });

  it('dedupes spoken audio by normalized text', () => {
    markTurnReplySpoken('Sending your care request now.');
    expect(turnReplyAlreadySpoken('Sending your care request now.')).toBe(true);
    expect(turnReplyAlreadySpoken('  Sending your care request now.  ')).toBe(true);
    expect(turnReplyAlreadySpoken('Different line')).toBe(false);
  });

  it('reset clears stages and spoken state', () => {
    claimTurnStage('reply_text', 'r3');
    markTurnReplySpoken('hi');
    resetTurnStream();
    expect(claimTurnStage('reply_text', 'r3')).toBe(true);
    expect(turnReplyAlreadySpoken('hi')).toBe(false);
  });
});

describe('resolveCaregiverFromMatch', () => {
  it('resolves by rank, id, and fuzzy name', async () => {
    const { resolveCaregiverFromMatch, resolveCaregiverFromAction } = await import(
      './resolveCaregiver'
    );
    const results = [
      {
        caregiver_id: 10,
        rank: 1,
        score: 0.9,
        breakdown: { cbf: 0.5, cf: 0.2, geo: 0.2, trust: 0.1 },
        explanation: 'top',
        display_name: 'Mohamed Rizwan',
        specialties: [],
        languages: ['English'],
        care_levels: ['basic'],
      },
      {
        caregiver_id: 20,
        rank: 2,
        score: 0.8,
        breakdown: { cbf: 0.4, cf: 0.2, geo: 0.2, trust: 0.1 },
        explanation: 'second',
        display_name: 'Nimal Perera',
        specialties: [],
        languages: ['Sinhala'],
        care_levels: ['basic'],
      },
    ];

    expect(resolveCaregiverFromMatch(results, { rank: 2 })?.caregiver_id).toBe(20);
    expect(resolveCaregiverFromMatch(results, { caregiverId: 10 })?.rank).toBe(1);
    expect(resolveCaregiverFromMatch(results, { nameQuery: 'rizwan' })?.caregiver_id).toBe(10);
    expect(
      resolveCaregiverFromAction(results, {
        type: 'request',
        caregiver_id: null,
        rank: null,
        name_query: '',
      })?.rank,
    ).toBe(1);
  });
});

describe('executeSerahAction request', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('enqueues a care request for the resolved hit', async () => {
    const enqueue = vi.fn(async () => ({ queued: false, item: null }));
    vi.doMock('../lib/outbox/flush', () => ({
      enqueueCareRequest: enqueue,
    }));

    const { useAssistant } = await import('./store');
    useAssistant.getState().reset();
    useAssistant.getState().setMatch({
      request_id: 99,
      latency_ms: 1,
      query: 'fever',
      emergency: false,
      weights: { cbf: 0.4, cf: 0.3, geo: 0.2, trust: 0.1 },
      results: [
        {
          caregiver_id: 42,
          rank: 1,
          score: 0.91,
          breakdown: { cbf: 0.5, cf: 0.2, geo: 0.2, trust: 0.1 },
          explanation: 'strong match',
          display_name: 'Mohamed Rizwan',
          specialties: ['fever'],
          languages: ['English'],
          care_levels: ['basic'],
        },
      ],
    });

    const { executeSerahAction } = await import('./executeSerahAction');
    const result = await executeSerahAction({
      type: 'request',
      caregiver_id: 42,
      rank: 1,
      name_query: '',
    });

    expect(result?.ok).toBe(true);
    expect(enqueue).toHaveBeenCalledOnce();
    expect(enqueue.mock.calls[0]?.[0]).toMatchObject({
      caregiver_id: 42,
      match_run_id: 99,
    });
    expect(useAssistant.getState().bookingStage).toBe('requested');
    expect(useAssistant.getState().focusedCaregiverId).toBe(42);
  });

  it('sets focus for view_profile without enqueueing', async () => {
    const enqueue = vi.fn();
    vi.doMock('../lib/outbox/flush', () => ({
      enqueueCareRequest: enqueue,
    }));

    const { useAssistant } = await import('./store');
    useAssistant.getState().reset();
    useAssistant.getState().setMatch({
      request_id: 1,
      latency_ms: 1,
      query: 'x',
      emergency: false,
      weights: { cbf: 0.4, cf: 0.3, geo: 0.2, trust: 0.1 },
      results: [
        {
          caregiver_id: 7,
          rank: 1,
          score: 0.5,
          breakdown: { cbf: 0.5, cf: 0.2, geo: 0.2, trust: 0.1 },
          explanation: 'ok',
          display_name: 'Asha',
          specialties: [],
          languages: [],
          care_levels: [],
        },
      ],
    });

    const { executeSerahAction } = await import('./executeSerahAction');
    const result = await executeSerahAction({ type: 'view_profile', rank: 1, name_query: '' });
    expect(result?.ok).toBe(true);
    expect(enqueue).not.toHaveBeenCalled();
    expect(useAssistant.getState().focusedCaregiverId).toBe(7);
    expect(useAssistant.getState().bookingStage).toBe('profile');
  });
});
