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
  PaymentIntent,
  PushSubscriptionResult,
  SignedDownloadUrl,
  Shift,
  VapidPublicKey,
  ConsentRow,
  ConsentState,
  HealthResponse,
  MatchResponse,
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
  type VoiceIntentInput,
} from './schemas';

export type ApiClientOptions = {
  baseUrl: string;
  getAccessToken?: () => string | null;
  getRefreshToken?: () => string | null;
  /** Called after a successful token refresh (access, and refresh if rotated). */
  onTokensRefreshed?: (tokens: { access: string; refresh?: string }) => void;
  /** Called when refresh fails — clear session / redirect to login. */
  onAuthFailure?: () => void;
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

export function createApiClient(options: ApiClientOptions) {
  const { baseUrl, getAccessToken, getRefreshToken, onTokensRefreshed, onAuthFailure } = options;
  let refreshInFlight: Promise<string | null> | null = null;

  async function refreshAccessToken(): Promise<string | null> {
    if (refreshInFlight) return refreshInFlight;
    refreshInFlight = (async () => {
      const refresh = getRefreshToken?.();
      if (!refresh) return null;
      try {
        const res = await fetch(`${baseUrl.replace(/\/$/, '')}/auth/token/refresh/`, {
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
          onAuthFailure?.();
          return null;
        }
        // Refresh may return only { access } unless rotation is enabled.
        const access =
          data && typeof data === 'object' && 'access' in data
            ? String((data as { access: unknown }).access)
            : '';
        if (!access) {
          onAuthFailure?.();
          return null;
        }
        const nextRefresh =
          data && typeof data === 'object' && 'refresh' in data
            ? String((data as { refresh: unknown }).refresh)
            : undefined;
        onTokensRefreshed?.({ access, refresh: nextRefresh });
        return access;
      } catch {
        onAuthFailure?.();
        return null;
      } finally {
        refreshInFlight = null;
      }
    })();
    return refreshInFlight;
  }

  async function request<T>(
    path: string,
    init: RequestInit = {},
    parse: (data: unknown) => T,
    retried = false,
  ): Promise<T> {
    const headers = new Headers(init.headers);
    if (!headers.has('Content-Type') && init.body && !(init.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }
    const token = getAccessToken?.();
    if (token) headers.set('Authorization', `Bearer ${token}`);

    const res = await fetch(`${baseUrl.replace(/\/$/, '')}${path}`, {
      ...init,
      headers,
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
    if (res.status === 401 && !retried && getRefreshToken && !path.includes('/auth/token')) {
      const next = await refreshAccessToken();
      if (next) {
        return request(path, init, parse, true);
      }
    }
    if (!res.ok) {
      throw new ApiError(`HTTP ${res.status}`, res.status, data);
    }
    return parse(data);
  }

  return {
    health: () => request('/health/', {}, (d) => HealthResponse.parse(d)),
    me: () => request('/auth/me/', {}, (d) => User.parse(d)),
    login: (email: string, password: string) =>
      request('/auth/token/', { method: 'POST', body: JSON.stringify({ email, password }) }, (d) =>
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
    voiceSession: () =>
      request('/voice/session/', {}, (d) => VoiceSessionResponse.parse(d)),
    clearVoiceSession: () =>
      request(
        '/voice/session/clear/',
        { method: 'POST', body: JSON.stringify({}) },
        (d) => VoiceSessionClearResponse.parse(d),
      ),
    dialoguePolicy: () =>
      request('/voice/policy/', {}, (d) => DialoguePolicy.parse(d)),
    getConsent: () => request('/consent/', {}, (d) => ConsentState.parse(d)),
    setConsent: (scope: string, granted: boolean) =>
      request('/consent/', { method: 'POST', body: JSON.stringify({ scope, granted }) }, (d) =>
        ConsentRow.parse(d),
      ),
    getNotificationPreferences: () =>
      request('/notification-preferences/', {}, (d) => NotificationPreferences.parse(d)),
    updateNotificationPreferences: (input: NotificationPreferencesUpdate) =>
      request(
        '/notification-preferences/',
        { method: 'PATCH', body: JSON.stringify(input) },
        (d) => NotificationPreferences.parse(d),
      ),
    getVapidPublicKey: () =>
      request('/push/vapid-public-key/', {}, (d) => VapidPublicKey.parse(d)),
    subscribeWebPush: (input: PushSubscriptionInput) =>
      request(
        '/push/subscriptions/',
        { method: 'POST', body: JSON.stringify(input) },
        (d) => PushSubscriptionResult.parse(d),
      ),
    unsubscribeWebPush: (endpoint: string) =>
      request(
        '/push/subscriptions/',
        { method: 'DELETE', body: JSON.stringify({ endpoint }) },
        (d) => z.object({ deleted: z.number() }).parse(d),
      ),
    registerMobilePushDevice: (input: MobilePushDeviceInput) =>
      request(
        '/push/mobile/devices/',
        { method: 'POST', body: JSON.stringify(input) },
        (d) => MobilePushDeviceResult.parse(d),
      ),
    unregisterMobilePushDevice: (token: string) =>
      request(
        '/push/mobile/devices/',
        { method: 'DELETE', body: JSON.stringify({ token }) },
        (d) => z.object({ deleted: z.number() }).parse(d),
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
      request(
        `/caregivers/me/availability-slots/${id}/`,
        { method: 'DELETE' },
        (d) => z.any().optional().parse(d),
      ),
    listCaregiverAvailabilitySlots: (caregiverId: number) =>
      request(`/caregivers/${caregiverId}/availability-slots/`, {}, (d) =>
        z.array(CaregiverAvailabilitySlot).parse(d),
      ),
    listShifts: () =>
      request('/shifts/', {}, (d) => z.array(Shift).parse(d)),
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
      request(
        `/users/${id}/`,
        { method: 'PATCH', body: JSON.stringify({ is_active }) },
        (d) => AdminUser.parse(d),
      ),
    getAdminAnalytics: (windowDays?: number) => {
      const qs = windowDays != null ? `?window_days=${windowDays}` : '';
      return request(`/admin/analytics/${qs}`, {}, (d) => AdminAnalytics.parse(d));
    },
    ingestHealthMetric: (input: HealthMetricIngestInput) =>
      request(
        '/health/metrics/ingest/',
        { method: 'POST', body: JSON.stringify(input) },
        (d) => HealthMetric.parse(d),
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
    caregiver: (id: number) =>
      request(`/caregivers/${id}/`, {}, (d) => CaregiverDetail.parse(d)),
    myCaregiverProfile: () =>
      request('/caregivers/me/', {}, (d) => CaregiverMeProfile.parse(d)),
    updateMyCaregiverProfile: (input: CaregiverProfileUpdate) =>
      request(
        '/caregivers/me/',
        { method: 'PATCH', body: JSON.stringify(input) },
        (d) => CaregiverMeProfile.parse(d),
      ),
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
      request(
        '/patients/me/',
        { method: 'PATCH', body: JSON.stringify(input) },
        (d) => PatientProfile.parse(d),
      ),
    vocabConditions: () =>
      request('/vocab/conditions/', {}, (d) => ConditionListResponse.parse(d)),
    listCareRequests: (page?: number) => {
      const qs = page != null ? `?page=${page}` : '';
      return request(`/care-requests/${qs}`, {}, (d) => CareRequestListResponse.parse(d));
    },
    createCareRequest: (input: CareRequestCreate) =>
      request(
        '/care-requests/',
        { method: 'POST', body: JSON.stringify(input) },
        (d) => CareRequest.parse(d),
      ),
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
      return request(`/care-relationships/${qs}`, {}, (d) =>
        CareRelationshipListResponse.parse(d),
      );
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
      request(
        '/leads/',
        { method: 'POST', body: JSON.stringify(input) },
        (d) => Lead.parse(d),
      ),
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
      return request(`/catalog/packages/${qs}`, {}, (d) =>
        z.array(CarePackage).parse(d),
      );
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
      request(
        '/admin/vocab/conditions/',
        { method: 'POST', body: JSON.stringify(input) },
        (d) => AdminConditionTerm.parse(d),
      ),
    updateAdminCondition: (slug: string, input: Partial<AdminConditionInput>) =>
      request(
        `/admin/vocab/conditions/${encodeURIComponent(slug)}/`,
        { method: 'PATCH', body: JSON.stringify(input) },
        (d) => AdminConditionTerm.parse(d),
      ),
    deleteAdminCondition: (slug: string) =>
      request(`/admin/vocab/conditions/${encodeURIComponent(slug)}/`, { method: 'DELETE' }, () => undefined),
    listAdminPackages: (careLevel?: string) => {
      const qs = careLevel ? `?care_level=${encodeURIComponent(careLevel)}` : '';
      return request(`/admin/catalog/packages/${qs}`, {}, (d) => z.array(CarePackage).parse(d));
    },
    createAdminPackage: (input: Record<string, unknown>) =>
      request(
        '/admin/catalog/packages/',
        { method: 'POST', body: JSON.stringify(input) },
        (d) => CarePackage.parse(d),
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
      request(
        '/admin/catalog/addons/',
        { method: 'POST', body: JSON.stringify(input) },
        (d) => CatalogAddOn.parse(d),
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
      request(
        '/checkout/',
        { method: 'POST', body: JSON.stringify(input) },
        (d) => Order.parse(d),
      ),
    getOrder: (id: number) =>
      request(`/orders/${id}/`, {}, (d) => Order.parse(d)),
    getOrderReceiptHtml: (id: number) =>
      request(`/orders/${id}/receipt/`, {}, (d) => String(d)),
    createPaymentIntent: (orderId: number) =>
      request(
        `/orders/${orderId}/payment-intent/`,
        { method: 'POST', body: JSON.stringify({}) },
        (d) => PaymentIntent.parse(d),
      ),
    getPaymentIntent: (orderId: number) =>
      request(`/orders/${orderId}/payment-intent/`, {}, (d) => PaymentIntent.parse(d)),
    confirmMockPayment: (providerIntentId: string) =>
      request(
        `/payments/mock/${encodeURIComponent(providerIntentId)}/confirm/`,
        { method: 'POST', body: JSON.stringify({}) },
        (d) => PaymentIntent.parse(d),
      ),
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
      return request(
        '/medical-records/',
        { method: 'POST', body: form, headers: {} },
        (d) => MedicalRecordDetail.parse(d),
      );
    },
    getMedicalRecord: (id: number) =>
      request(`/medical-records/${id}/`, {}, (d) => MedicalRecordDetail.parse(d)),
    updateMedicalRecord: (id: number, input: MedicalRecordUpdateInput) =>
      request(
        `/medical-records/${id}/`,
        { method: 'PATCH', body: JSON.stringify(input) },
        (d) => MedicalRecordDetail.parse(d),
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
      request('/message-threads/current/', {}, (d) =>
        d == null ? null : MessageThread.parse(d),
      ),
    listMessages: (threadId: number, params?: { after_id?: number; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.after_id != null) qs.set('after_id', String(params.after_id));
      if (params?.limit != null) qs.set('limit', String(params.limit));
      const q = qs.toString();
      return request(
        `/message-threads/${threadId}/messages/${q ? `?${q}` : ''}`,
        {},
        (d) => z.array(Message).parse(d),
      );
    },
    sendMessage: (threadId: number, body: string) =>
      request(
        `/message-threads/${threadId}/messages/`,
        { method: 'POST', body: JSON.stringify({ body }) },
        (d) => Message.parse(d),
      ),
    markMessagesRead: (threadId: number, lastReadMessageId: number) =>
      request(
        `/message-threads/${threadId}/read/`,
        { method: 'POST', body: JSON.stringify({ last_read_message_id: lastReadMessageId }) },
        (d) => MessageReadResult.parse(d),
      ),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
