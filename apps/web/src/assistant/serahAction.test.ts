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
    const enqueue = vi.fn(async () => ({
      queued: false,
      result: { id: 501, caregiver_id: 42, status: 'pending' },
    }));
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
    expect(useAssistant.getState().bookingStage).toBe('awaiting_accept');
    expect(useAssistant.getState().focusedCaregiverId).toBe(42);
    expect(useAssistant.getState().careRequestId).toBe(501);
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
    expect(useAssistant.getState().profileNarrateMode).toBe('brief');
  });

  it('sets detail narrate mode for describe_caregiver', async () => {
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
    const result = await executeSerahAction({
      type: 'describe_caregiver',
      rank: 1,
      name_query: '',
    });
    expect(result?.ok).toBe(true);
    expect(useAssistant.getState().focusedCaregiverId).toBe(7);
    expect(useAssistant.getState().profileNarrateMode).toBe('detail');
  });
});

describe('careRequestStatus helpers', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('picks the next ranked caregiver after a reject', async () => {
    const { nextRankedCaregiver } = await import('./careRequestStatus');
    const results = [
      {
        caregiver_id: 10,
        rank: 1,
        score: 0.9,
        breakdown: { cbf: 0.5, cf: 0.2, geo: 0.2, trust: 0.1 },
        explanation: 'top',
        display_name: 'A',
        specialties: [],
        languages: [],
        care_levels: [],
      },
      {
        caregiver_id: 20,
        rank: 2,
        score: 0.8,
        breakdown: { cbf: 0.4, cf: 0.2, geo: 0.2, trust: 0.1 },
        explanation: 'second',
        display_name: 'B',
        specialties: [],
        languages: [],
        care_levels: [],
      },
    ];
    expect(nextRankedCaregiver(results, 10)?.caregiver_id).toBe(20);
    expect(nextRankedCaregiver(results, 20)).toBeNull();
  });

  it('advances to packages on accept and offers next on reject', async () => {
    vi.doMock('./useTts', () => ({
      speakSerah: vi.fn(async () => undefined),
      stopSpeaking: vi.fn(),
    }));
    vi.doMock('../auth/api', () => ({
      api: {
        listCarePackages: vi.fn(async () => [
          {
            id: 1,
            slug: 'basic-home-care',
            name: 'Basic Home Care',
            description: '',
            care_level: 'basic',
            price_lkr: '8500',
            default_days: 7,
            sort_order: 10,
          },
        ]),
        listCatalogAddOns: vi.fn(async () => []),
        listCareRequests: vi.fn(async () => ({ results: [] })),
      },
    }));

    const { useAssistant } = await import('./store');
    const {
      applyCareRequestTerminalStatus,
      acceptedNarration,
    } = await import('./careRequestStatus');
    const { resetCatalogCache } = await import('./voiceCheckout');
    resetCatalogCache();

    useAssistant.getState().reset();
    useAssistant.getState().setMatch({
      request_id: 1,
      latency_ms: 1,
      query: 'x',
      emergency: false,
      weights: { cbf: 0.4, cf: 0.3, geo: 0.2, trust: 0.1 },
      results: [
        {
          caregiver_id: 10,
          rank: 1,
          score: 0.9,
          breakdown: { cbf: 0.5, cf: 0.2, geo: 0.2, trust: 0.1 },
          explanation: 'top',
          display_name: 'Asha',
          specialties: [],
          languages: [],
          care_levels: [],
        },
        {
          caregiver_id: 20,
          rank: 2,
          score: 0.8,
          breakdown: { cbf: 0.4, cf: 0.2, geo: 0.2, trust: 0.1 },
          explanation: 'next',
          display_name: 'Nimal',
          specialties: [],
          languages: [],
          care_levels: [],
        },
      ],
    });
    useAssistant.getState().setCareRequestId(77);
    useAssistant.getState().setBookingStage('awaiting_accept');
    useAssistant.getState().setFocusedCaregiverId(10);

    expect(
      applyCareRequestTerminalStatus({
        id: 77,
        patient_email: 'p@example.com',
        caregiver_id: 10,
        caregiver_name: 'Asha',
        status: 'accepted',
        message: '',
        match_snapshot: {},
        expires_at: '2099-01-01T00:00:00Z',
        relationship_status: 'pending_payment',
      }),
    ).toBe(true);
    expect(useAssistant.getState().bookingStage).toBe('packages');
    expect(useAssistant.getState().chat.at(-1)?.text).toBe(acceptedNarration('Asha'));

    useAssistant.getState().setCareRequestId(78);
    useAssistant.getState().setBookingStage('awaiting_accept');
    useAssistant.getState().setFocusedCaregiverId(10);
    expect(
      applyCareRequestTerminalStatus({
        id: 78,
        patient_email: 'p@example.com',
        caregiver_id: 10,
        caregiver_name: 'Asha',
        status: 'rejected',
        message: '',
        match_snapshot: {},
        expires_at: '2099-01-01T00:00:00Z',
      }),
    ).toBe(true);
    expect(useAssistant.getState().careRequestId).toBeNull();
    expect(useAssistant.getState().focusedCaregiverId).toBe(20);
    expect(useAssistant.getState().bookingStage).toBe('profile');
    expect(useAssistant.getState().chat.at(-1)?.text).toMatch(/Nimal/);
  });
});

describe('resolvePackage', () => {
  const packages = [
    {
      id: 1,
      slug: 'basic-home-care',
      name: 'Basic Home Care',
      description: '',
      care_level: 'basic' as const,
      price_lkr: '8500',
      default_days: 7,
      sort_order: 10,
    },
    {
      id: 2,
      slug: 'intermediate-nursing',
      name: 'Intermediate Nursing',
      description: '',
      care_level: 'intermediate' as const,
      price_lkr: '14500',
      default_days: 7,
      sort_order: 20,
    },
    {
      id: 3,
      slug: 'advanced-clinical',
      name: 'Advanced Clinical Care',
      description: '',
      care_level: 'advanced' as const,
      price_lkr: '22000',
      default_days: 7,
      sort_order: 30,
    },
  ];

  const addons = [
    {
      id: 10,
      slug: 'meal-support',
      name: 'Meal support',
      description: '',
      category: 'food' as const,
      price_lkr: '2500',
      sort_order: 20,
    },
    {
      id: 11,
      slug: 'hospital-escort',
      name: 'Hospital escort',
      description: '',
      category: 'hospital' as const,
      price_lkr: '3500',
      sort_order: 10,
    },
  ];

  it('resolves by id, rank, name, and standard→basic', async () => {
    const { resolvePackage, parseDaysFromText, resolveAddOns } = await import(
      './resolvePackage'
    );
    expect(resolvePackage(packages, { packageId: 2 })?.slug).toBe('intermediate-nursing');
    expect(resolvePackage(packages, { rank: 1 })?.slug).toBe('basic-home-care');
    expect(resolvePackage(packages, { nameQuery: 'intermediate' })?.id).toBe(2);
    expect(resolvePackage(packages, { nameQuery: 'standard' })?.slug).toBe('basic-home-care');
    expect(parseDaysFromText('Basic for 7 days with meals')).toBe(7);
    expect(parseDaysFromText('a week of care')).toBe(7);
    expect(resolveAddOns(addons, { nameQuery: 'with meals' }).map((a) => a.slug)).toEqual([
      'meal-support',
    ]);
  });
});

describe('executeSerahAction select_package / confirm_checkout', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('updates checkoutDraft on select_package', async () => {
    vi.doMock('./useTts', () => ({
      speakSerah: vi.fn(async () => undefined),
      stopSpeaking: vi.fn(),
    }));
    vi.doMock('../auth/api', () => ({
      api: {
        listCarePackages: vi.fn(async () => [
          {
            id: 1,
            slug: 'basic-home-care',
            name: 'Basic Home Care',
            description: '',
            care_level: 'basic',
            price_lkr: '8500',
            default_days: 7,
            sort_order: 10,
          },
        ]),
        listCatalogAddOns: vi.fn(async () => [
          {
            id: 10,
            slug: 'meal-support',
            name: 'Meal support',
            description: '',
            category: 'food',
            price_lkr: '2500',
            sort_order: 20,
          },
        ]),
        createCheckout: vi.fn(),
      },
    }));

    const { resetCatalogCache } = await import('./voiceCheckout');
    resetCatalogCache();
    const { useAssistant } = await import('./store');
    useAssistant.getState().reset();
    useAssistant.getState().setCareRequestId(99);
    useAssistant.getState().setBookingStage('packages');

    const { executeSerahAction } = await import('./executeSerahAction');
    const result = await executeSerahAction({
      type: 'select_package',
      package_id: 'basic',
      name_query: 'basic with meals',
      days: 7,
      addon_query: 'meals',
      addon_ids: [],
    });

    expect(result?.ok).toBe(true);
    expect(useAssistant.getState().checkoutDraft).toMatchObject({
      packageId: 1,
      packageName: 'Basic Home Care',
      days: 7,
      addonIds: [10],
    });
    expect(useAssistant.getState().bookingStage).toBe('packages');
  });

  it('cancels pending request and resets booking on cancel_flow', async () => {
    const cancelCareRequest = vi.fn(async () => ({
      id: 501,
      patient_email: 'p@example.com',
      caregiver_id: 42,
      caregiver_name: 'Mohamed Rizwan',
      status: 'cancelled',
      message: '',
      match_snapshot: {},
      expires_at: '2099-01-01T00:00:00Z',
    }));

    vi.doMock('../auth/api', () => ({
      api: {
        cancelCareRequest,
        listCareRequests: vi.fn(),
        listCarePackages: vi.fn(async () => []),
        listCatalogAddOns: vi.fn(async () => []),
      },
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
          caregiver_id: 42,
          rank: 1,
          score: 0.9,
          breakdown: { cbf: 0.5, cf: 0.2, geo: 0.2, trust: 0.1 },
          explanation: 'top',
          display_name: 'Mohamed Rizwan',
          specialties: [],
          languages: [],
          care_levels: [],
        },
      ],
    });
    useAssistant.getState().setFocusedCaregiverId(42);
    useAssistant.getState().setCareRequestId(501);
    useAssistant.getState().setBookingStage('awaiting_accept');
    useAssistant.getState().setCheckoutDraft({
      packageId: 1,
      packageName: 'Basic',
      addonIds: [2],
      days: 7,
      orderId: null,
    });

    const { executeSerahAction } = await import('./executeSerahAction');
    const result = await executeSerahAction({ type: 'cancel_flow' });

    expect(result?.ok).toBe(true);
    expect(cancelCareRequest).toHaveBeenCalledWith(501);
    expect(useAssistant.getState().bookingStage).toBe('idle');
    expect(useAssistant.getState().focusedCaregiverId).toBeNull();
    expect(useAssistant.getState().careRequestId).toBeNull();
    expect(useAssistant.getState().checkoutDraft.packageId).toBeNull();
    expect(useAssistant.getState().match?.results).toHaveLength(1);
    expect(useAssistant.getState().chat.at(-1)?.text).toMatch(/cancelled that care request/i);
  });

  it('closes drawer without API cancel when no pending request', async () => {
    const cancelCareRequest = vi.fn();
    vi.doMock('../auth/api', () => ({
      api: { cancelCareRequest },
    }));

    const { useAssistant } = await import('./store');
    useAssistant.getState().reset();
    useAssistant.getState().setFocusedCaregiverId(7);
    useAssistant.getState().setBookingStage('profile');

    const { executeSerahAction } = await import('./executeSerahAction');
    const result = await executeSerahAction({ type: 'cancel_flow' });

    expect(result?.ok).toBe(true);
    expect(cancelCareRequest).not.toHaveBeenCalled();
    expect(useAssistant.getState().bookingStage).toBe('idle');
    expect(useAssistant.getState().focusedCaregiverId).toBeNull();
  });

  it('posts checkout and navigates to pay without charging', async () => {
    const createCheckout = vi.fn(async () => ({
      id: 555,
      care_request_id: 99,
      patient_id: 1,
      status: 'awaiting_payment',
      days: 7,
      currency: 'LKR',
      subtotal_lkr: '59500',
      total_lkr: '59500',
      lines: [],
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    }));
    const navigate = vi.fn();

    vi.doMock('./useTts', () => ({
      speakSerah: vi.fn(async () => undefined),
      stopSpeaking: vi.fn(),
    }));
    vi.doMock('../auth/api', () => ({
      api: {
        listCarePackages: vi.fn(async () => [
          {
            id: 1,
            slug: 'basic-home-care',
            name: 'Basic Home Care',
            description: '',
            care_level: 'basic',
            price_lkr: '8500',
            default_days: 7,
            sort_order: 10,
          },
        ]),
        listCatalogAddOns: vi.fn(async () => []),
        createCheckout,
      },
    }));
    vi.doMock('../auth/session', () => ({
      loadCachedUser: () => ({
        id: 1,
        email: 'p@example.com',
        role: 'patient',
        first_name: 'P',
        last_name: 'T',
        otp_enabled: false,
        otp_verified: true,
      }),
    }));
    vi.doMock('./appNavigate', () => ({
      appNavigate: navigate,
      bindAppNavigate: vi.fn(),
    }));

    const { resetCatalogCache } = await import('./voiceCheckout');
    resetCatalogCache();
    const { useAssistant } = await import('./store');
    useAssistant.getState().reset();
    useAssistant.getState().setCareRequestId(99);
    useAssistant.getState().setCheckoutDraft({
      packageId: 1,
      packageName: 'Basic Home Care',
      addonIds: [],
      days: 7,
      orderId: null,
    });
    useAssistant.getState().setBookingStage('packages');

    const { executeSerahAction } = await import('./executeSerahAction');
    const result = await executeSerahAction({ type: 'confirm_checkout' });

    expect(result?.ok).toBe(true);
    expect(createCheckout).toHaveBeenCalledWith({
      care_request_id: 99,
      package_id: 1,
      addon_ids: [],
      days: 7,
    });
    expect(navigate).toHaveBeenCalledWith('/orders/555/pay');
    expect(useAssistant.getState().bookingStage).toBe('pay');
    expect(useAssistant.getState().checkoutDraft.orderId).toBe(555);
    expect(useAssistant.getState().chat.at(-1)?.text).toMatch(/tap Pay/i);
  });
});
