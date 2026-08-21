import { z } from 'zod';
import {
  CaregiverDetail,
  CaregiverListResponse,
  CaregiverMeProfile,
  CaregiverAvailabilitySlot,
  CareRequest,
  CareRequestListResponse,
  CareRelationship,
  CareRelationshipListResponse,
  ConditionListResponse,
  AdminConditionTerm,
  AdminConditionListResponse,
  AdminAnalytics,
  AuditLogListResponse,
  Lead,
  LeadListResponse,
  CarePackage,
  CatalogAddOn,
  MedicalRecordAttachment,
  MedicalRecordDetail,
  MedicalRecordList,
  HealthMetric,
  HealthMetricWindow,
  Message,
  MessageReadResult,
  MessageThread,
  MobilePushDeviceResult,
  NotificationPreferences,
  Order,
  OtpRequestResult,
  PaymentIntent,
  PushSubscriptionResult,
  SignedDownloadUrl,
  Shift,
  VapidPublicKey,
  ConsentRow,
  ConsentState,
  HealthResponse,
  MatchResponse,
  MatchHistoryEntry,
  MatchHistoryListResponse,
  PatientProfile,
  RegisterResponse,
  TokenPair,
  User,
  AdminUser,
  AdminUserListResponse,
  VoiceIntent,
  VoiceSessionClearResponse,
  VoiceSessionResponse,
  VoiceTurnResponse,
  VoiceTtsResponse,
  DialoguePolicy,
  type CaregiverListParams,
  type CaregiverAvailabilitySlotInput,
  type CaregiverProfileUpdate,
  type CareRequestCreate,
  type CheckoutCreate,
  type LeadCreate,
  type MatchInput,
  type MedicalRecordCreateInput,
  type MedicalRecordUpdateInput,
  type HealthMetricIngestInput,
  type MobilePushDeviceInput,
  type NotificationPreferencesUpdate,
  type PatientProfileUpdate,
  type PushSubscriptionInput,
  type RegisterInput,
  type ShiftCreateInput,
  type AdminUserListParams,
  type AdminConditionInput,
  type AuditLogListParams,
  type VoiceIntentInput,
} from './schemas';
import { TimeoutError, fetchWithTimeout, isNetworkError, withRetry } from './http';

export type ApiClientOptions = {
  baseUrl: string;
  getAccessToken?: () => string | null;
  getRefreshToken?: () => string | null;
  /** Called after a successful token refresh (access, and refresh if rotated). */
  onTokensRefreshed?: (tokens: { access: string; refresh?: string }) => void;
  /** Called when refresh fails with an auth response — clear session / redirect to login. */
  onAuthFailure?: () => void;
  /** Default request timeout in ms (Step 82). Default 30s. */
  timeoutMs?: number;
  /** Extra retries after the first attempt for idempotent GETs on transport failure. Default 2. */
  maxRetries?: number;
  /** Fired after each completed attempt (success or typed transport failure). */
  onRequestOutcome?: (outcome: 'ok' | 'network' | 'timeout' | 'http') => void;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export { NetworkError, TimeoutError, isNetworkError } from './http';
export { isTimeoutError } from './http';

export function createApiClient(options: ApiClientOptions) {
  const {
    baseUrl,
    getAccessToken,
    getRefreshToken,
    onTokensRefreshed,
    onAuthFailure,
    timeoutMs = 30_000,
    maxRetries = 2,
    onRequestOutcome,
  } = options;
  let refreshInFlight: Promise<string | null> | null = null;

  function noteOutcome(outcome: 'ok' | 'network' | 'timeout' | 'http') {
    onRequestOutcome?.(outcome);
  }

  async function doFetch(path: string, init: RequestInit): Promise<Response> {
    return fetchWithTimeout(`${baseUrl.replace(/\/$/, '')}${path}`, init, { timeoutMs });
  }

  async function refreshAccessToken(): Promise<string | null> {
    if (refreshInFlight) return refreshInFlight;
    refreshInFlight = (async () => {
      const refresh = getRefreshToken?.();
      if (!refresh) return null;
      try {
        const res = await doFetch('/auth/token/refresh/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh }),
        });
        const text = await res.text();
        let data: unknown = null;
        if (text) {
          try {
            data = JSON.parse(text);
          } catch {
            data = text;
          }
        }
        if (!res.ok) {
          // Only clear session when the server rejects the refresh token.
          if (res.status === 401 || res.status === 403) onAuthFailure?.();
          noteOutcome('http');
          return null;
        }
        // Refresh may return only { access } unless rotation is enabled.
        const access =
          data && typeof data === 'object' && 'access' in data
            ? String((data as { access: unknown }).access)
            : '';
        if (!access) {
          onAuthFailure?.();
          noteOutcome('http');
          return null;
        }
        const nextRefresh =
          data && typeof data === 'object' && 'refresh' in data
            ? String((data as { refresh: unknown }).refresh)
            : undefined;
        onTokensRefreshed?.({ access, refresh: nextRefresh });
        noteOutcome('ok');
        return access;
      } catch (err) {
        // Transport failure — keep tokens; caller decides whether session is stale.
        noteOutcome(err instanceof TimeoutError ? 'timeout' : 'network');
        return null;
      } finally {
        refreshInFlight = null;
      }
    })();
    return refreshInFlight;
  }

  async function requestOnce<T>(
    path: string,
    init: RequestInit,
    parse: (data: unknown) => T,
    retried: boolean,
  ): Promise<T> {
    const headers = new Headers(init.headers);
    if (!headers.has('Content-Type') && init.body && !(init.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }
    const token = getAccessToken?.();
    if (token) headers.set('Authorization', `Bearer ${token}`);

    const res = await doFetch(path, { ...init, headers });
    const text = await res.text();
    let data: unknown = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = text;
      }
    }
    if (res.status === 401 && !retried && getRefreshToken && !path.includes('/auth/token')) {
      const next = await refreshAccessToken();
      if (next) {
        return requestOnce(path, init, parse, true);
      }
    }
    if (!res.ok) {
      noteOutcome('http');
      throw new ApiError(`HTTP ${res.status}`, res.status, data);
    }
    noteOutcome('ok');
    return parse(data);
  }

  async function request<T>(
    path: string,
    init: RequestInit = {},
    parse: (data: unknown) => T,
    retried = false,
  ): Promise<T> {
    try {
      return await withRetry(
        typeof init.method === 'string' ? init.method : 'GET',
        () => requestOnce(path, init, parse, retried),
        { maxRetries },
      );
    } catch (err) {
      if (err instanceof TimeoutError) noteOutcome('timeout');
      else if (isNetworkError(err)) noteOutcome('network');
      throw err;
    }
  }

  async function requestBlobOnce(path: string, init: RequestInit, retried: boolean): Promise<Blob> {
    const headers = new Headers(init.headers);
    const token = getAccessToken?.();
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const res = await doFetch(path, { ...init, headers });
    if (res.status === 401 && !retried && getRefreshToken && !path.includes('/auth/token')) {
      const next = await refreshAccessToken();
      if (next) return requestBlobOnce(path, init, true);
    }
    if (!res.ok) {
      const text = await res.text();
      let data: unknown = text;
      try {
        data = JSON.parse(text);
      } catch {
        /* keep text */
      }
      noteOutcome('http');
      throw new ApiError(`HTTP ${res.status}`, res.status, data);
    }
    noteOutcome('ok');
    return res.blob();
  }

  async function requestBlob(path: string, init: RequestInit = {}, retried = false): Promise<Blob> {
    try {
      return await withRetry(
        typeof init.method === 'string' ? init.method : 'GET',
        () => requestBlobOnce(path, init, retried),
        { maxRetries },
      );
    } catch (err) {
      if (err instanceof TimeoutError) noteOutcome('timeout');
      else if (isNetworkError(err)) noteOutcome('network');
      throw err;
    }
  }

  return {
    health: () => request('/health/', {}, (d) => HealthResponse.parse(d)),
    me: () => request('/auth/me/', {}, (d) => User.parse(d)),
    login: (email: string, password: string) =>
      request('/auth/token/', { method: 'POST', body: JSON.stringify({ email, password }) }, (d) =>
        TokenPair.parse(d),
      ),
    requestOtp: () =>
      request('/auth/otp/request/', { method: 'POST', body: JSON.stringify({}) }, (d) =>
        OtpRequestResult.parse(d),
      ),
    verifyOtp: (code: string) =>
      request('/auth/otp/verify/', { method: 'POST', body: JSON.stringify({ code }) }, (d) =>
        TokenPair.parse(d),
      ),
    register: (input: RegisterInput) =>
      request(
        '/auth/register/',
        {
          method: 'POST',
          body: JSON.stringify({
            email: input.email,
            password: input.password,
            role: input.role ?? 'patient',
            first_name: input.first_name ?? '',
            last_name: input.last_name ?? '',
          }),
        },
        (d) => RegisterResponse.parse(d),
      ),
    voiceIntent: (input: VoiceIntentInput) =>
      request(
        '/voice/intent/',
        {
          method: 'POST',
          body: JSON.stringify({
            text: input.text,
            ...(input.language ? { language: input.language } : {}),
          }),
        },
        (d) => VoiceIntent.parse(d),
      ),
    /**
     * Conversational turn: optional Web Speech text + recorded audio.
     * Audio is preferred for Sinhala/Tamil (server Whisper ASR).
     * ``uiLanguage`` locks ASR + Serah reply language.
     */
    voiceTurn: (input: {
      text?: string;
      audio?: Blob | null;
      hasPriorMatch?: boolean;
      priorIntent?: Record<string, unknown> | null;
      priorMatch?: Record<string, unknown> | null;
      uiLanguage?: 'Sinhala' | 'Tamil' | 'English';
    }) => {
      const form = new FormData();
      if (input.text) form.append('text', input.text);
      if (input.audio) form.append('audio', input.audio, 'turn.webm');
      form.append('has_prior_match', input.hasPriorMatch ? 'true' : 'false');
      if (input.priorIntent) form.append('prior_intent', JSON.stringify(input.priorIntent));
      if (input.priorMatch) form.append('prior_match', JSON.stringify(input.priorMatch));
      if (input.uiLanguage) form.append('ui_language', input.uiLanguage);
      return request(
        '/voice/turn/',
        {
          method: 'POST',
          body: form,
          headers: {}, // let browser set multipart boundary
        },
        (d) => VoiceTurnResponse.parse(d),
      );
    },
    voiceTts: (input: { text: string; replyLang?: string }) =>
      request(
        '/voice/tts/',
        {
          method: 'POST',
          body: JSON.stringify({
            text: input.text,
            reply_lang: input.replyLang || 'en-US',
          }),
        },
        (d) => VoiceTtsResponse.parse(d),
      ),
    voiceSession: () => request('/voice/session/', {}, (d) => VoiceSessionResponse.parse(d)),
    clearVoiceSession: () =>
      request('/voice/session/clear/', { method: 'POST', body: JSON.stringify({}) }, (d) =>
        VoiceSessionClearResponse.parse(d),
      ),
    dialoguePolicy: () => request('/voice/policy/', {}, (d) => DialoguePolicy.parse(d)),
    getConsent: () => request('/consent/', {}, (d) => ConsentState.parse(d)),
    setConsent: (scope: string, granted: boolean) =>
      request('/consent/', { method: 'POST', body: JSON.stringify({ scope, granted }) }, (d) =>
        ConsentRow.parse(d),
      ),
    getNotificationPreferences: () =>
      request('/notification-preferences/', {}, (d) => NotificationPreferences.parse(d)),
    updateNotificationPreferences: (input: NotificationPreferencesUpdate) =>
      request('/notification-preferences/', { method: 'PATCH', body: JSON.stringify(input) }, (d) =>
        NotificationPreferences.parse(d),
      ),
    exportPrivacyData: (format: 'json' | 'pdf' = 'json') => {
      if (format === 'pdf') {
        return requestBlob(`/privacy/export/?export_format=pdf`);
      }
      return request(
        `/privacy/export/?export_format=json`,
        {},
        (d) => d as Record<string, unknown>,
      );
    },
    eraseAccount: (password: string, confirm = 'erase') =>
      request(
        '/privacy/erase/',
        { method: 'POST', body: JSON.stringify({ password, confirm }) },
        (d) =>
          z
            .object({
              erased: z.boolean(),
              user_id: z.number(),
              erased_at: z.string(),
              faiss_rebuilt: z.boolean(),
              stats: z.record(z.number()).optional(),
            })
            .parse(d),
      ),
    getVapidPublicKey: () => request('/push/vapid-public-key/', {}, (d) => VapidPublicKey.parse(d)),
    subscribeWebPush: (input: PushSubscriptionInput) =>
      request('/push/subscriptions/', { method: 'POST', body: JSON.stringify(input) }, (d) =>
        PushSubscriptionResult.parse(d),
      ),
    unsubscribeWebPush: (endpoint: string) =>
      request(
        '/push/subscriptions/',
        { method: 'DELETE', body: JSON.stringify({ endpoint }) },
        (d) => z.object({ deleted: z.number() }).parse(d),
      ),
    registerMobilePushDevice: (input: MobilePushDeviceInput) =>
      request('/push/mobile/devices/', { method: 'POST', body: JSON.stringify(input) }, (d) =>
        MobilePushDeviceResult.parse(d),
      ),
    unregisterMobilePushDevice: (token: string) =>
      request('/push/mobile/devices/', { method: 'DELETE', body: JSON.stringify({ token }) }, (d) =>
        z.object({ deleted: z.number() }).parse(d),
      ),
    listMyAvailabilitySlots: () =>
      request('/caregivers/me/availability-slots/', {}, (d) =>
        z.array(CaregiverAvailabilitySlot).parse(d),
      ),
    createMyAvailabilitySlot: (input: CaregiverAvailabilitySlotInput) =>
      request(
        '/caregivers/me/availability-slots/',
        { method: 'POST', body: JSON.stringify(input) },
        (d) => CaregiverAvailabilitySlot.parse(d),
      ),
    updateMyAvailabilitySlot: (id: number, input: Partial<CaregiverAvailabilitySlotInput>) =>
      request(
        `/caregivers/me/availability-slots/${id}/`,
        { method: 'PATCH', body: JSON.stringify(input) },
        (d) => CaregiverAvailabilitySlot.parse(d),
      ),
    deleteMyAvailabilitySlot: (id: number) =>
      request(`/caregivers/me/availability-slots/${id}/`, { method: 'DELETE' }, (d) =>
        z.any().optional().parse(d),
      ),
    listCaregiverAvailabilitySlots: (caregiverId: number) =>
      request(`/caregivers/${caregiverId}/availability-slots/`, {}, (d) =>
        z.array(CaregiverAvailabilitySlot).parse(d),
      ),
    listShifts: () => request('/shifts/', {}, (d) => z.array(Shift).parse(d)),
    createShift: (input: ShiftCreateInput) =>
      request('/shifts/', { method: 'POST', body: JSON.stringify(input) }, (d) => Shift.parse(d)),
    getShift: (id: number) => request(`/shifts/${id}/`, {}, (d) => Shift.parse(d)),
    cancelShift: (id: number) =>
      request(`/shifts/${id}/`, { method: 'DELETE' }, (d) => Shift.parse(d)),
    listAdminUsers: (params: AdminUserListParams = {}) => {
      const qs = new URLSearchParams();
      if (params.role) qs.set('role', params.role);
      if (params.is_active != null) qs.set('is_active', String(params.is_active));
      if (params.q) qs.set('q', params.q);
      if (params.page != null) qs.set('page', String(params.page));
      if (params.page_size != null) qs.set('page_size', String(params.page_size));
      const suffix = qs.toString() ? `?${qs.toString()}` : '';
      return request(`/users/${suffix}`, {}, (d) => AdminUserListResponse.parse(d));
    },
    setAdminUserActive: (id: number, is_active: boolean) =>
      request(`/users/${id}/`, { method: 'PATCH', body: JSON.stringify({ is_active }) }, (d) =>
        AdminUser.parse(d),
      ),
    getAdminAnalytics: (windowDays?: number) => {
      const qs = windowDays != null ? `?window_days=${windowDays}` : '';
      return request(`/admin/analytics/${qs}`, {}, (d) => AdminAnalytics.parse(d));
    },
    listAuditLogs: (params: AuditLogListParams = {}) => {
      const qs = new URLSearchParams();
      if (params.actor) qs.set('actor', params.actor);
      if (params.action) qs.set('action', params.action);
      if (params.date_from) qs.set('date_from', params.date_from);
      if (params.date_to) qs.set('date_to', params.date_to);
      if (params.request_id) qs.set('request_id', params.request_id);
      if (params.page != null) qs.set('page', String(params.page));
      if (params.page_size != null) qs.set('page_size', String(params.page_size));
      const suffix = qs.toString() ? `?${qs.toString()}` : '';
      return request(`/audit/${suffix}`, {}, (d) => AuditLogListResponse.parse(d));
    },
    exportAuditLogsCsv: async (params: AuditLogListParams = {}) => {
      const qs = new URLSearchParams();
      if (params.actor) qs.set('actor', params.actor);
      if (params.action) qs.set('action', params.action);
      if (params.date_from) qs.set('date_from', params.date_from);
      if (params.date_to) qs.set('date_to', params.date_to);
      if (params.request_id) qs.set('request_id', params.request_id);
      const suffix = qs.toString() ? `?${qs.toString()}` : '';
      return request(`/audit/export/${suffix}`, {}, (d) => String(d));
    },
    ingestHealthMetric: (input: HealthMetricIngestInput) =>
      request('/health/metrics/ingest/', { method: 'POST', body: JSON.stringify(input) }, (d) =>
        HealthMetric.parse(d),
      ),
    healthMetricWindow: (params: { kind: string; hours?: number; patient_id?: number }) => {
      const qs = new URLSearchParams();
      qs.set('kind', params.kind);
      if (params.hours != null) qs.set('hours', String(params.hours));
      if (params.patient_id != null) qs.set('patient_id', String(params.patient_id));
      const q = qs.toString();
      return request(`/health/metrics/window/?${q}`, {}, (d) => HealthMetricWindow.parse(d));
    },
    match: (input: MatchInput) =>
      request(
        '/match/',
        {
          method: 'POST',
          body: JSON.stringify({
            condition: input.condition ?? '',
            language: input.language ?? '',
            care_level: input.care_level ?? '',
            query: input.query ?? '',
            ...(input.longitude != null && input.latitude != null
              ? { longitude: input.longitude, latitude: input.latitude }
              : {}),
            ...(input.k != null ? { k: input.k } : {}),
            ...(input.emergency != null ? { emergency: input.emergency } : {}),
          }),
        },
        (d) => MatchResponse.parse(d),
      ),
    listMatchHistory: (page?: number) => {
      const qs = page != null ? `?page=${page}` : '';
      return request(`/match/history/${qs}`, {}, (d) => MatchHistoryListResponse.parse(d));
    },
    deleteMatchHistory: (id: number) =>
      request(`/match/history/${id}/`, { method: 'DELETE' }, () => undefined),
    caregivers: (params: CaregiverListParams = {}) => {
      const qs = new URLSearchParams();
      if (params.q) qs.set('q', params.q);
      if (params.language) qs.set('language', params.language);
      if (params.specialty) qs.set('specialty', params.specialty);
      if (params.city) qs.set('city', params.city);
      if (params.care_level) qs.set('care_level', params.care_level);
      if (params.available != null) qs.set('available', String(params.available));
      if (params.near) qs.set('near', params.near);
      if (params.radius_km != null) qs.set('radius_km', String(params.radius_km));
      if (params.page != null) qs.set('page', String(params.page));
      if (params.page_size != null) qs.set('page_size', String(params.page_size));
      const suffix = qs.toString() ? `?${qs}` : '';
      return request(`/caregivers/${suffix}`, {}, (d) => CaregiverListResponse.parse(d));
    },
    caregiver: (id: number) => request(`/caregivers/${id}/`, {}, (d) => CaregiverDetail.parse(d)),
    myCaregiverProfile: () => request('/caregivers/me/', {}, (d) => CaregiverMeProfile.parse(d)),
    updateMyCaregiverProfile: (input: CaregiverProfileUpdate) =>
      request('/caregivers/me/', { method: 'PATCH', body: JSON.stringify(input) }, (d) =>
        CaregiverMeProfile.parse(d),
      ),
    uploadMyCaregiverPhoto: (file: Blob, filename?: string) => {
      const form = new FormData();
      form.append('file', file, filename ?? 'photo.jpg');
      return request('/caregivers/me/photo/', { method: 'POST', body: form, headers: {} }, (d) =>
        CaregiverMeProfile.parse(d),
      );
    },
    uploadMyCaregiverDocument: (file: Blob, filename?: string) => {
      const form = new FormData();
      form.append('file', file, filename ?? 'document');
      return request(
        '/caregivers/me/documents/',
        { method: 'POST', body: form, headers: {} },
        (d) => CaregiverMeProfile.parse(d),
      );
    },
    setMyAvailability: (is_available: boolean) =>
      request(
        '/caregivers/me/',
        {
          method: 'PATCH',
          body: JSON.stringify({ is_available }),
        },
        (d) => CaregiverMeProfile.parse(d),
      ),
    myPatientProfile: () => request('/patients/me/', {}, (d) => PatientProfile.parse(d)),
    updateMyPatientProfile: (input: PatientProfileUpdate) =>
      request('/patients/me/', { method: 'PATCH', body: JSON.stringify(input) }, (d) =>
        PatientProfile.parse(d),
      ),
    uploadMyPatientPhoto: (file: Blob, filename?: string) => {
      const form = new FormData();
      form.append('file', file, filename ?? 'photo.jpg');
      return request('/patients/me/photo/', { method: 'POST', body: form, headers: {} }, (d) =>
        PatientProfile.parse(d),
      );
    },
    vocabConditions: () => request('/vocab/conditions/', {}, (d) => ConditionListResponse.parse(d)),
    listCareRequests: (page?: number) => {
      const qs = page != null ? `?page=${page}` : '';
      return request(`/care-requests/${qs}`, {}, (d) => CareRequestListResponse.parse(d));
    },
    createCareRequest: (input: CareRequestCreate) => {
      const headers: Record<string, string> = {};
      if (input.idempotency_key) {
        headers['Idempotency-Key'] = input.idempotency_key;
      }
      return request(
        '/care-requests/',
        { method: 'POST', body: JSON.stringify(input), headers },
        (d) => CareRequest.parse(d),
      );
    },
    cancelCareRequest: (id: number) =>
      request(
        `/care-requests/${id}/action/`,
        { method: 'PATCH', body: JSON.stringify({ action: 'cancel' }) },
        (d) => CareRequest.parse(d),
      ),
    acceptCareRequest: (id: number) =>
      request(
        `/care-requests/${id}/action/`,
        { method: 'PATCH', body: JSON.stringify({ action: 'accept' }) },
        (d) => CareRequest.parse(d),
      ),
    rejectCareRequest: (id: number, reason?: string) =>
      request(
        `/care-requests/${id}/action/`,
        {
          method: 'PATCH',
          body: JSON.stringify({ action: 'reject', reason: reason ?? '' }),
        },
        (d) => CareRequest.parse(d),
      ),
    listCareRelationships: (page?: number) => {
      const qs = page != null ? `?page=${page}` : '';
      return request(`/care-relationships/${qs}`, {}, (d) => CareRelationshipListResponse.parse(d));
    },
    currentCareRelationship: () =>
      request('/care-relationships/current/', {}, (d) =>
        d == null ? null : CareRelationship.parse(d),
      ),
    activateCareRelationship: (id: number) =>
      request(
        `/care-relationships/${id}/action/`,
        { method: 'PATCH', body: JSON.stringify({ action: 'activate' }) },
        (d) => CareRelationship.parse(d),
      ),
    endCareRelationship: (id: number, reason?: string) =>
      request(
        `/care-relationships/${id}/action/`,
        {
          method: 'PATCH',
          body: JSON.stringify({ action: 'end', reason: reason ?? '' }),
        },
        (d) => CareRelationship.parse(d),
      ),
    createLead: (input: LeadCreate) =>
      request('/leads/', { method: 'POST', body: JSON.stringify(input) }, (d) => Lead.parse(d)),
    listLeads: (page?: number, statusFilter?: string) => {
      const params = new URLSearchParams();
      if (page != null) params.set('page', String(page));
      if (statusFilter) params.set('status', statusFilter);
      const qs = params.toString() ? `?${params.toString()}` : '';
      return request(`/leads/${qs}`, {}, (d) => LeadListResponse.parse(d));
    },
    markLeadContacted: (id: number, notes?: string) =>
      request(
        `/leads/${id}/contact/`,
        {
          method: 'PATCH',
          body: JSON.stringify({ action: 'contact', notes: notes ?? '' }),
        },
        (d) => Lead.parse(d),
      ),
    closeLead: (id: number, notes?: string) =>
      request(
        `/leads/${id}/contact/`,
        {
          method: 'PATCH',
          body: JSON.stringify({ action: 'close', notes: notes ?? '' }),
        },
        (d) => Lead.parse(d),
      ),
    listCarePackages: (careLevel?: string) => {
      const qs = careLevel ? `?care_level=${encodeURIComponent(careLevel)}` : '';
      return request(`/catalog/packages/${qs}`, {}, (d) => z.array(CarePackage).parse(d));
    },
    listCatalogAddOns: (category?: string) => {
      const qs = category ? `?category=${encodeURIComponent(category)}` : '';
      return request(`/catalog/addons/${qs}`, {}, (d) => z.array(CatalogAddOn).parse(d));
    },
    listAdminConditions: (active?: boolean) => {
      const qs = active == null ? '' : `?active=${active}`;
      return request(`/admin/vocab/conditions/${qs}`, {}, (d) =>
        AdminConditionListResponse.parse(d),
      );
    },
    createAdminCondition: (input: AdminConditionInput) =>
      request('/admin/vocab/conditions/', { method: 'POST', body: JSON.stringify(input) }, (d) =>
        AdminConditionTerm.parse(d),
      ),
    updateAdminCondition: (slug: string, input: Partial<AdminConditionInput>) =>
      request(
        `/admin/vocab/conditions/${encodeURIComponent(slug)}/`,
        { method: 'PATCH', body: JSON.stringify(input) },
        (d) => AdminConditionTerm.parse(d),
      ),
    deleteAdminCondition: (slug: string) =>
      request(
        `/admin/vocab/conditions/${encodeURIComponent(slug)}/`,
        { method: 'DELETE' },
        () => undefined,
      ),
    listAdminPackages: (careLevel?: string) => {
      const qs = careLevel ? `?care_level=${encodeURIComponent(careLevel)}` : '';
      return request(`/admin/catalog/packages/${qs}`, {}, (d) => z.array(CarePackage).parse(d));
    },
    createAdminPackage: (input: Record<string, unknown>) =>
      request('/admin/catalog/packages/', { method: 'POST', body: JSON.stringify(input) }, (d) =>
        CarePackage.parse(d),
      ),
    updateAdminPackage: (id: number, input: Record<string, unknown>) =>
      request(
        `/admin/catalog/packages/${id}/`,
        { method: 'PATCH', body: JSON.stringify(input) },
        (d) => CarePackage.parse(d),
      ),
    deleteAdminPackage: (id: number) =>
      request(`/admin/catalog/packages/${id}/`, { method: 'DELETE' }, () => undefined),
    listAdminAddOns: (category?: string) => {
      const qs = category ? `?category=${encodeURIComponent(category)}` : '';
      return request(`/admin/catalog/addons/${qs}`, {}, (d) => z.array(CatalogAddOn).parse(d));
    },
    createAdminAddOn: (input: Record<string, unknown>) =>
      request('/admin/catalog/addons/', { method: 'POST', body: JSON.stringify(input) }, (d) =>
        CatalogAddOn.parse(d),
      ),
    updateAdminAddOn: (id: number, input: Record<string, unknown>) =>
      request(
        `/admin/catalog/addons/${id}/`,
        { method: 'PATCH', body: JSON.stringify(input) },
        (d) => CatalogAddOn.parse(d),
      ),
    deleteAdminAddOn: (id: number) =>
      request(`/admin/catalog/addons/${id}/`, { method: 'DELETE' }, () => undefined),
    createCheckout: (input: CheckoutCreate) =>
      request('/checkout/', { method: 'POST', body: JSON.stringify(input) }, (d) => Order.parse(d)),
    getOrder: (id: number) => request(`/orders/${id}/`, {}, (d) => Order.parse(d)),
    getOrderReceiptHtml: (id: number) => request(`/orders/${id}/receipt/`, {}, (d) => String(d)),
    createPaymentIntent: (orderId: number) =>
      request(
        `/orders/${orderId}/payment-intent/`,
        { method: 'POST', body: JSON.stringify({}) },
        (d) => PaymentIntent.parse(d),
      ),
    getPaymentIntent: (orderId: number) =>
      request(`/orders/${orderId}/payment-intent/`, {}, (d) => PaymentIntent.parse(d)),
    confirmMockPayment: (providerIntentId: string, idempotencyKey?: string) => {
      const headers: Record<string, string> = {};
      if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
      return request(
        `/payments/mock/${encodeURIComponent(providerIntentId)}/confirm/`,
        {
          method: 'POST',
          body: JSON.stringify(idempotencyKey ? { idempotency_key: idempotencyKey } : {}),
          headers,
        },
        (d) => PaymentIntent.parse(d),
      );
    },
    listMedicalRecords: (params?: { patient_id?: number }) => {
      const qs = params?.patient_id != null ? `?patient_id=${params.patient_id}` : '';
      return request(`/medical-records/${qs}`, {}, (d) => z.array(MedicalRecordList).parse(d));
    },
    createMedicalRecord: (input: MedicalRecordCreateInput) => {
      const form = new FormData();
      form.append('condition_slug', input.condition_slug);
      form.append('title', input.title);
      if (input.description != null) form.append('description', input.description);
      if (input.sensitive_notes != null) form.append('sensitive_notes', input.sensitive_notes);
      if (input.recorded_at != null) form.append('recorded_at', input.recorded_at);
      if (input.file instanceof Blob) form.append('file', input.file);
      return request('/medical-records/', { method: 'POST', body: form, headers: {} }, (d) =>
        MedicalRecordDetail.parse(d),
      );
    },
    getMedicalRecord: (id: number) =>
      request(`/medical-records/${id}/`, {}, (d) => MedicalRecordDetail.parse(d)),
    updateMedicalRecord: (id: number, input: MedicalRecordUpdateInput) =>
      request(`/medical-records/${id}/`, { method: 'PATCH', body: JSON.stringify(input) }, (d) =>
        MedicalRecordDetail.parse(d),
      ),
    deleteMedicalRecord: (id: number) =>
      request(`/medical-records/${id}/`, { method: 'DELETE' }, () => undefined),
    uploadMedicalRecordAttachment: (recordId: number, file: Blob, filename?: string) => {
      const form = new FormData();
      form.append('file', file, filename ?? 'attachment');
      return request(
        `/medical-records/${recordId}/attachments/`,
        { method: 'POST', body: form, headers: {} },
        (d) => MedicalRecordAttachment.parse(d),
      );
    },
    getMedicalRecordAttachmentDownloadUrl: (attachmentId: number) =>
      request(
        `/medical-records/attachments/${attachmentId}/download-url/`,
        { method: 'POST', body: JSON.stringify({}) },
        (d) => SignedDownloadUrl.parse(d),
      ),
    currentMessageThread: () =>
      request('/message-threads/current/', {}, (d) => (d == null ? null : MessageThread.parse(d))),
    listMessages: (threadId: number, params?: { after_id?: number; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.after_id != null) qs.set('after_id', String(params.after_id));
      if (params?.limit != null) qs.set('limit', String(params.limit));
      const q = qs.toString();
      return request(`/message-threads/${threadId}/messages/${q ? `?${q}` : ''}`, {}, (d) =>
        z.array(Message).parse(d),
      );
    },
    sendMessage: (threadId: number, body: string, idempotencyKey?: string) => {
      const headers: Record<string, string> = {};
      if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
      const payload: { body: string; idempotency_key?: string } = { body };
      if (idempotencyKey) payload.idempotency_key = idempotencyKey;
      return request(
        `/message-threads/${threadId}/messages/`,
        { method: 'POST', body: JSON.stringify(payload), headers },
        (d) => Message.parse(d),
      );
    },
    markMessagesRead: (threadId: number, lastReadMessageId: number) =>
      request(
        `/message-threads/${threadId}/read/`,
        { method: 'POST', body: JSON.stringify({ last_read_message_id: lastReadMessageId }) },
        (d) => MessageReadResult.parse(d),
      ),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
