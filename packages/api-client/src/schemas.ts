import { z } from 'zod';

export const HealthResponse = z.object({
  status: z.enum(['ok', 'degraded']),
  db: z.string(),
  redis: z.string(),
});
export type HealthResponse = z.infer<typeof HealthResponse>;

export const User = z.object({
  id: z.number(),
  email: z.string().email(),
  role: z.enum(['patient', 'caregiver', 'admin', 'auditor']),
  first_name: z.string(),
  last_name: z.string(),
});
export type User = z.infer<typeof User>;

export const AdminUser = z.object({
  id: z.number(),
  email: z.string().email(),
  role: z.enum(['patient', 'caregiver', 'admin', 'auditor']),
  first_name: z.string(),
  last_name: z.string(),
  is_active: z.boolean(),
  date_joined: z.string(),
  last_login: z.string().nullable().optional(),
});
export type AdminUser = z.infer<typeof AdminUser>;

export const AdminUserListResponse = z.object({
  count: z.number(),
  next: z.string().nullable().optional(),
  previous: z.string().nullable().optional(),
  results: z.array(AdminUser),
});
export type AdminUserListResponse = z.infer<typeof AdminUserListResponse>;

export type AdminUserListParams = {
  role?: string;
  is_active?: boolean;
  q?: string;
  page?: number;
  page_size?: number;
};

export const TokenPair = z.object({
  access: z.string(),
  refresh: z.string(),
});
export type TokenPair = z.infer<typeof TokenPair>;

export const RegisterResponse = z.object({
  id: z.number(),
  email: z.string().email(),
  role: z.enum(['patient', 'caregiver', 'admin', 'auditor']),
  first_name: z.string(),
  last_name: z.string(),
});
export type RegisterResponse = z.infer<typeof RegisterResponse>;

export const RegisterInput = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  role: z.enum(['patient', 'caregiver']).default('patient'),
  first_name: z.string().optional(),
  last_name: z.string().optional(),
});
export type RegisterInput = z.infer<typeof RegisterInput>;

export const VoiceLanguage = z.enum(['Sinhala', 'Tamil', 'English']);
export type VoiceLanguage = z.infer<typeof VoiceLanguage>;

export const VoiceIntentInput = z.object({
  text: z.string().min(1).max(2000),
  language: VoiceLanguage.optional(),
});
export type VoiceIntentInput = z.infer<typeof VoiceIntentInput>;

export const VoiceIntent = z.object({
  id: z.number(),
  raw_text: z.string(),
  condition: z.string(),
  language: VoiceLanguage,
  /** All languages mixed in the utterance (Singlish / Tanglish). */
  languages: z.array(VoiceLanguage).optional().default([]),
  care_level: z.enum(['basic', 'intermediate', 'advanced']),
  urgency: z.enum(['routine', 'urgent', 'critical']),
  source: z.string(),
  ts: z.string(),
});
export type VoiceIntent = z.infer<typeof VoiceIntent>;

/** The AI-consent scope that gates the voice → intent pipeline. */
export const AI_CONSENT_SCOPE = 'ai_processing' as const;

export const ConsentState = z.object({
  scopes: z.record(z.string()),
  current: z.record(z.boolean()),
});
export type ConsentState = z.infer<typeof ConsentState>;

export const ConsentRow = z.object({
  id: z.number(),
  scope: z.string(),
  granted: z.boolean(),
  ts: z.string(),
});
export type ConsentRow = z.infer<typeof ConsentRow>;

export const NotificationEventPreference = z.object({
  key: z.string(),
  label: z.string(),
  description: z.string(),
  category: z.enum(['security', 'transactional', 'marketing']),
  locked: z.boolean(),
  email: z.boolean(),
  push: z.boolean(),
});
export type NotificationEventPreference = z.infer<typeof NotificationEventPreference>;

export const NotificationPreferences = z.object({
  channels: z.object({
    email: z.record(z.boolean()),
    push: z.record(z.boolean()),
  }),
  events: z.array(NotificationEventPreference),
});
export type NotificationPreferences = z.infer<typeof NotificationPreferences>;

export const NotificationPreferencesUpdate = z.object({
  email: z.record(z.boolean()).optional(),
  push: z.record(z.boolean()).optional(),
});
export type NotificationPreferencesUpdate = z.infer<typeof NotificationPreferencesUpdate>;

export const VapidPublicKey = z.object({
  public_key: z.string(),
  configured: z.boolean(),
});
export type VapidPublicKey = z.infer<typeof VapidPublicKey>;

export const PushSubscriptionInput = z.object({
  endpoint: z.string(),
  keys: z.object({
    p256dh: z.string(),
    auth: z.string(),
  }),
  user_agent: z.string().optional(),
});
export type PushSubscriptionInput = z.infer<typeof PushSubscriptionInput>;

export const PushSubscriptionResult = z.object({
  id: z.number(),
  endpoint: z.string(),
  created: z.boolean(),
});
export type PushSubscriptionResult = z.infer<typeof PushSubscriptionResult>;

export const HealthMetric = z.object({
  id: z.number(),
  patient: z.number(),
  kind: z.enum(['heart_rate', 'blood_glucose', 'spo2']),
  value: z.number(),
  unit: z.string().optional().default(''),
  source: z.string().optional().default('manual'),
  recorded_at: z.string(),
  metadata: z.record(z.string(), z.unknown()).optional().default({}),
  created_at: z.string(),
});
export type HealthMetric = z.infer<typeof HealthMetric>;

export const HealthMetricIngestInput = z.object({
  patient_id: z.number().optional(),
  kind: z.enum(['heart_rate', 'blood_glucose', 'spo2']),
  value: z.number(),
  unit: z.string().optional(),
  source: z.string().optional(),
  recorded_at: z.string().optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});
export type HealthMetricIngestInput = z.infer<typeof HealthMetricIngestInput>;

export const HealthMetricWindow = z.object({
  kind: z.string(),
  window_hours: z.number(),
  count: z.number(),
  min: z.number().nullable().optional(),
  max: z.number().nullable().optional(),
  avg: z.number().nullable().optional(),
  latest: z
    .object({
      value: z.number(),
      unit: z.string().optional().default(''),
      source: z.string().optional().default('manual'),
      recorded_at: z.string(),
    })
    .nullable()
    .optional(),
  series: z.array(
    z.object({
      bucket: z.string(),
      avg: z.number().nullable().optional(),
      count: z.number(),
    }),
  ),
});
export type HealthMetricWindow = z.infer<typeof HealthMetricWindow>;

export const MobilePushDeviceInput = z.object({
  token: z.string().min(1),
  platform: z.enum(['fcm', 'apns']).optional().default('fcm'),
  device_id: z.string().optional(),
  app_version: z.string().optional(),
});
export type MobilePushDeviceInput = z.infer<typeof MobilePushDeviceInput>;

export const MobilePushDeviceResult = z.object({
  id: z.number(),
  token: z.string(),
  platform: z.enum(['fcm', 'apns']),
  created: z.boolean(),
});
export type MobilePushDeviceResult = z.infer<typeof MobilePushDeviceResult>;

export const CaregiverAvailabilitySlot = z.object({
  id: z.number(),
  caregiver: z.number(),
  weekday: z.number().int().min(0).max(6),
  weekday_label: z.string().optional(),
  start_time: z.string(),
  end_time: z.string(),
  timezone: z.string().optional().default('Asia/Colombo'),
  is_active: z.boolean().optional().default(true),
  created_at: z.string(),
  updated_at: z.string(),
});
export type CaregiverAvailabilitySlot = z.infer<typeof CaregiverAvailabilitySlot>;

export const CaregiverAvailabilitySlotInput = z.object({
  weekday: z.number().int().min(0).max(6),
  start_time: z.string(),
  end_time: z.string(),
  timezone: z.string().optional(),
  is_active: z.boolean().optional(),
});
export type CaregiverAvailabilitySlotInput = z.infer<typeof CaregiverAvailabilitySlotInput>;

export const Shift = z.object({
  id: z.number(),
  caregiver: z.number(),
  caregiver_name: z.string().optional(),
  patient: z.number(),
  patient_email: z.string().email().optional(),
  availability_slot: z.number().nullable().optional(),
  starts_at: z.string(),
  ends_at: z.string(),
  timezone: z.string().optional().default('Asia/Colombo'),
  status: z.enum(['booked', 'cancelled']),
  notes: z.string().optional().default(''),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Shift = z.infer<typeof Shift>;

export const ShiftCreateInput = z.object({
  caregiver_id: z.number().int().positive(),
  starts_at: z.string(),
  ends_at: z.string(),
  availability_slot_id: z.number().int().positive().nullable().optional(),
  notes: z.string().optional(),
  timezone: z.string().optional(),
});
export type ShiftCreateInput = z.infer<typeof ShiftCreateInput>;

export const ShiftConflictFallback = z.object({
  caregiver_id: z.number(),
  display_name: z.string(),
  score: z.number(),
  explanation: z.string(),
  distance_m: z.number().nullable().optional(),
  availability_slot_id: z.number(),
  starts_at: z.string(),
  ends_at: z.string(),
  match_run_id: z.number(),
  specialties: z.array(z.string()).optional().default([]),
  languages: z.array(z.string()).optional().default([]),
  care_levels: z.array(z.string()).optional().default([]),
  trust_score: z.number().nullable().optional(),
});
export type ShiftConflictFallback = z.infer<typeof ShiftConflictFallback>;

export const ShiftConflictBody = z.object({
  detail: z.string().optional(),
  code: z.literal('shift_overlap').optional(),
  conflict: z.literal(true).optional(),
  fallback: ShiftConflictFallback.nullable().optional(),
});
export type ShiftConflictBody = z.infer<typeof ShiftConflictBody>;

export const MatchBreakdown = z.object({
  cbf: z.number(),
  cf: z.number(),
  geo: z.number(),
  trust: z.number(),
});
export type MatchBreakdown = z.infer<typeof MatchBreakdown>;

export const MatchHit = z.object({
  caregiver_id: z.number(),
  rank: z.number(),
  score: z.number(),
  breakdown: MatchBreakdown,
  explanation: z.string(),
  distance_m: z.number().nullable().optional(),
  display_name: z.string(),
  specialties: z.array(z.string()),
  languages: z.array(z.string()),
  care_levels: z.array(z.string()),
  trust_score: z.number().nullable().optional(),
  is_available: z.boolean().optional().default(true),
  /** Previous rank before a refine rematch (Step 15i). */
  previous_rank: z.number().nullable().optional(),
  /** previous_rank - rank; positive means moved up. */
  rank_delta: z.number().nullable().optional(),
});
export type MatchHit = z.infer<typeof MatchHit>;

export const MatchResponse = z.object({
  request_id: z.number(),
  latency_ms: z.number(),
  query: z.string(),
  emergency: z.boolean(),
  weights: MatchBreakdown,
  results: z.array(MatchHit),
  refined: z.boolean().optional().default(false),
});
export type MatchResponse = z.infer<typeof MatchResponse>;

export const VoiceTurnIntent = z.object({
  condition: z.string(),
  language: z.string(),
  languages: z.array(z.string()).optional().default([]),
  care_level: z.string(),
  urgency: z.string(),
  raw_text: z.string(),
  source: z.string().optional(),
});
export type VoiceTurnIntent = z.infer<typeof VoiceTurnIntent>;

export const VoiceTurnResponse = z.object({
  route: z.enum(['CHAT', 'MATCH', 'CLARIFY', 'REFINE', 'ACTION', 'EMERGENCY']),
  situation: z.string().optional().default(''),
  transcript: z.string(),
  asr_source: z.string(),
  asr_language: z.string().optional().default(''),
  asr_language_code: z.string().optional().default(''),
  reply: z.string(),
  reply_lang: z.string(),
  reply_audio_base64: z.string().optional().default(''),
  reply_audio_mime: z.string().optional().default(''),
  tts_source: z.string().optional().default(''),
  intent: VoiceTurnIntent.nullable(),
  match: MatchResponse.nullable().optional(),
  clear_match: z.boolean().optional().default(false),
  session_id: z.number().nullable().optional(),
  open_questions: z.array(z.string()).optional().default([]),
  chat_source: z.string().optional().default(''),
  chat_backend: z.string().optional().default(''),
  match_engine: z.string().optional().default(''),
});
export type VoiceTurnResponse = z.infer<typeof VoiceTurnResponse>;

export const DialogueSessionSnapshot = z.object({
  id: z.number(),
  lang: z.string(),
  intent_chips: z.record(z.string(), z.unknown()).optional().default({}),
  open_questions: z.array(z.string()).optional().default([]),
  route_history: z.array(z.record(z.string(), z.unknown())).optional().default([]),
  turns: z.array(z.record(z.string(), z.unknown())).optional().default([]),
  last_match_run_id: z.number().nullable().optional(),
  updated_at: z.string().optional(),
});
export type DialogueSessionSnapshot = z.infer<typeof DialogueSessionSnapshot>;

export const VoiceSessionResponse = z.object({
  active: z.boolean(),
  session: DialogueSessionSnapshot.nullable().optional(),
});
export type VoiceSessionResponse = z.infer<typeof VoiceSessionResponse>;

export const VoiceSessionClearResponse = z.object({
  cleared: z.number(),
  active: z.boolean(),
});
export type VoiceSessionClearResponse = z.infer<typeof VoiceSessionClearResponse>;

export const DialoguePolicy = z.object({
  chat_backend: z.string(),
  match_engine: z.string(),
  gemini_ranks_caregivers: z.boolean(),
  gemini_rate_limit: z.number(),
  gemini_rate_window_sec: z.number(),
  has_gemini_key: z.boolean(),
});
export type DialoguePolicy = z.infer<typeof DialoguePolicy>;

export const MatchInput = z.object({
  condition: z.string().optional(),
  language: z.string().optional(),
  care_level: z.string().optional(),
  query: z.string().optional(),
  longitude: z.number().optional(),
  latitude: z.number().optional(),
  k: z.number().int().min(1).max(25).optional(),
  emergency: z.boolean().optional(),
});
export type MatchInput = z.infer<typeof MatchInput>;

export const CaregiverProfile = z.object({
  id: z.number(),
  email: z.string(),
  display_name: z.string(),
  longitude: z.number().nullable(),
  latitude: z.number().nullable(),
  city: z.string().optional().default(''),
  certifications: z.array(z.string()),
  languages: z.array(z.string()),
  specialties: z.array(z.string()),
  care_levels: z.array(z.string()),
  trust_score: z.number(),
  bio: z.string().optional().default(''),
  is_active: z.boolean().optional(),
  is_available: z.boolean().optional().default(true),
  photo_url: z.string().nullable().optional(),
  created_at: z.string().optional(),
});
export type CaregiverProfile = z.infer<typeof CaregiverProfile>;

export const CaregiverMeProfile = CaregiverProfile.extend({
  nic_id: z.string().optional().default(''),
  years_experience: z.number().int().nullable().optional(),
  service_radius_km: z.number().optional().default(25),
  certification_docs: z
    .array(z.record(z.string(), z.unknown()))
    .optional()
    .default([]),
  is_approved: z.boolean().optional().default(false),
  completion_percent: z.number().int(),
  onboarding_complete: z.boolean(),
  is_match_eligible: z.boolean(),
  missing_fields: z.array(z.string()).optional().default([]),
  updated_at: z.string().optional(),
});
export type CaregiverMeProfile = z.infer<typeof CaregiverMeProfile>;

export const CaregiverProfileUpdate = z.object({
  display_name: z.string().optional(),
  nic_id: z.string().optional(),
  city: z.string().optional(),
  longitude: z.number().optional(),
  latitude: z.number().optional(),
  languages: z.array(z.string()).optional(),
  specialties: z.array(z.string()).optional(),
  care_levels: z.array(z.string()).optional(),
  certifications: z.array(z.string()).optional(),
  years_experience: z.number().int().optional(),
  service_radius_km: z.number().optional(),
  bio: z.string().optional(),
  certification_docs: z.array(z.record(z.string(), z.unknown())).optional(),
  is_available: z.boolean().optional(),
});
export type CaregiverProfileUpdate = z.infer<typeof CaregiverProfileUpdate>;

export const CaregiverDetail = CaregiverProfile.extend({
  approximate_area: z.string().optional().default(''),
  reviews_teaser: z
    .array(
      z.object({
        id: z.number().optional(),
        rating: z.number().optional(),
        comment: z.string().optional(),
        created_at: z.string().optional(),
      }),
    )
    .optional()
    .default([]),
  review_count: z.number().int().optional().default(0),
  review_average: z.number().nullable().optional(),
});
export type CaregiverDetail = z.infer<typeof CaregiverDetail>;

export const CaregiverListResponse = z.object({
  count: z.number(),
  next: z.string().nullable().optional(),
  previous: z.string().nullable().optional(),
  results: z.array(CaregiverProfile),
});
export type CaregiverListResponse = z.infer<typeof CaregiverListResponse>;

export const CaregiverListParams = z.object({
  q: z.string().optional(),
  language: z.string().optional(),
  specialty: z.string().optional(),
  city: z.string().optional(),
  care_level: z.string().optional(),
  available: z.union([z.boolean(), z.string()]).optional(),
  near: z.string().optional(),
  radius_km: z.number().optional(),
  page: z.number().int().optional(),
  page_size: z.number().int().optional(),
});
export type CaregiverListParams = z.infer<typeof CaregiverListParams>;

export const PatientProfile = z.object({
  id: z.number(),
  email: z.string(),
  display_name: z.string(),
  longitude: z.number().nullable(),
  latitude: z.number().nullable(),
  city: z.string().optional().default(''),
  preferred_language: z.string(),
  languages: z.array(z.string()).optional().default([]),
  conditions: z.array(z.string()).optional().default([]),
  care_level: z.string(),
  height_cm: z.number().nullable().optional(),
  weight_kg: z.number().nullable().optional(),
  blood_type: z.string().optional().default(''),
  medications: z.array(z.string()).optional().default([]),
  allergies: z.array(z.string()).optional().default([]),
  emergency_contact_name: z.string().optional().default(''),
  emergency_contact_phone: z.string().optional().default(''),
  photo_url: z.string().nullable().optional(),
  completion_percent: z.number().int(),
  can_request_care: z.boolean(),
  missing_fields: z.array(z.string()).optional().default([]),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
});
export type PatientProfile = z.infer<typeof PatientProfile>;

export const PatientProfileUpdate = z.object({
  display_name: z.string().optional(),
  city: z.string().optional(),
  longitude: z.number().optional(),
  latitude: z.number().optional(),
  preferred_language: z.string().optional(),
  languages: z.array(z.string()).optional(),
  conditions: z.array(z.string()).optional(),
  care_level: z.string().optional(),
  height_cm: z.number().int().optional(),
  weight_kg: z.number().optional(),
  blood_type: z.string().optional(),
  medications: z.array(z.string()).optional(),
  allergies: z.array(z.string()).optional(),
  emergency_contact_name: z.string().optional(),
  emergency_contact_phone: z.string().optional(),
});
export type PatientProfileUpdate = z.infer<typeof PatientProfileUpdate>;

export const CareRequestStatus = z.enum([
  'draft',
  'pending',
  'accepted',
  'rejected',
  'cancelled',
  'expired',
]);
export type CareRequestStatus = z.infer<typeof CareRequestStatus>;

export const CareRequest = z.object({
  id: z.number(),
  patient_email: z.string(),
  caregiver_id: z.number(),
  caregiver_name: z.string(),
  status: CareRequestStatus,
  message: z.string().optional().default(''),
  match_run: z.number().nullable().optional(),
  match_snapshot: z.record(z.string(), z.unknown()).optional().default({}),
  expires_at: z.string(),
  responded_at: z.string().nullable().optional(),
  relationship_id: z.number().nullable().optional(),
  relationship_status: z
    .enum(['pending_payment', 'active', 'ended'])
    .nullable()
    .optional(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
});
export type CareRequest = z.infer<typeof CareRequest>;

export const CareRequestListResponse = z.object({
  count: z.number(),
  next: z.string().nullable().optional(),
  previous: z.string().nullable().optional(),
  results: z.array(CareRequest),
});
export type CareRequestListResponse = z.infer<typeof CareRequestListResponse>;

export const CareRequestCreate = z.object({
  caregiver_id: z.number(),
  message: z.string().optional(),
  match_run_id: z.number().optional(),
  match_snapshot: z.record(z.string(), z.unknown()).optional(),
});
export type CareRequestCreate = z.infer<typeof CareRequestCreate>;

export const CareRelationshipStatus = z.enum(['pending_payment', 'active', 'ended']);
export type CareRelationshipStatus = z.infer<typeof CareRelationshipStatus>;

export const CareRelationship = z.object({
  id: z.number(),
  patient_email: z.string(),
  patient_display_name: z.string().optional(),
  caregiver_id: z.number(),
  caregiver_name: z.string(),
  care_request: z.number().nullable().optional(),
  status: CareRelationshipStatus,
  is_primary: z.boolean(),
  started_at: z.string(),
  ended_at: z.string().nullable().optional(),
  end_reason: z.string().optional().default(''),
});
export type CareRelationship = z.infer<typeof CareRelationship>;

export const CareRelationshipListResponse = z.object({
  count: z.number(),
  next: z.string().nullable().optional(),
  previous: z.string().nullable().optional(),
  results: z.array(CareRelationship),
});
export type CareRelationshipListResponse = z.infer<typeof CareRelationshipListResponse>;

export const LeadStatus = z.enum(['new', 'contacted', 'closed']);
export type LeadStatus = z.infer<typeof LeadStatus>;

export const Lead = z.object({
  id: z.number(),
  name: z.string(),
  email: z.string(),
  phone: z.string().optional().default(''),
  message: z.string().optional().default(''),
  city: z.string().optional().default(''),
  preferred_language: z.string().optional().default(''),
  source: z.string().optional().default('marketing_form'),
  status: LeadStatus,
  contacted_at: z.string().nullable().optional(),
  contacted_by_email: z.string().nullable().optional(),
  admin_notes: z.string().optional().default(''),
  ack_email_sent: z.boolean().optional(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
});
export type Lead = z.infer<typeof Lead>;

export const LeadCreate = z.object({
  name: z.string(),
  email: z.string().email(),
  phone: z.string().optional(),
  message: z.string().optional(),
  city: z.string().optional(),
  preferred_language: z.string().optional(),
  source: z.string().optional(),
});
export type LeadCreate = z.infer<typeof LeadCreate>;

export const LeadListResponse = z.object({
  count: z.number(),
  next: z.string().nullable().optional(),
  previous: z.string().nullable().optional(),
  results: z.array(Lead),
});
export type LeadListResponse = z.infer<typeof LeadListResponse>;

export const CarePackage = z.object({
  id: z.number(),
  slug: z.string(),
  name: z.string(),
  description: z.string().optional().default(''),
  care_level: z.enum(['basic', 'intermediate', 'advanced']),
  price_lkr: z.union([z.string(), z.number()]),
  default_days: z.number().int(),
  is_active: z.boolean().optional(),
  sort_order: z.number().int().optional(),
});
export type CarePackage = z.infer<typeof CarePackage>;

export const CatalogAddOn = z.object({
  id: z.number(),
  slug: z.string(),
  name: z.string(),
  description: z.string().optional().default(''),
  category: z.enum(['hospital', 'food', 'transport', 'supplies', 'other']),
  price_lkr: z.union([z.string(), z.number()]),
  is_active: z.boolean().optional(),
  sort_order: z.number().int().optional(),
});
export type CatalogAddOn = z.infer<typeof CatalogAddOn>;

export const OrderStatus = z.enum(['awaiting_payment', 'paid', 'cancelled', 'expired']);
export type OrderStatus = z.infer<typeof OrderStatus>;

export const OrderLineKind = z.enum(['package', 'addon']);
export type OrderLineKind = z.infer<typeof OrderLineKind>;

export const OrderLineItem = z.object({
  id: z.number(),
  kind: OrderLineKind,
  catalog_id: z.number(),
  slug: z.string(),
  name: z.string(),
  unit_price_lkr: z.union([z.string(), z.number()]),
  quantity: z.number().int(),
  line_total_lkr: z.union([z.string(), z.number()]),
});
export type OrderLineItem = z.infer<typeof OrderLineItem>;

export const Order = z.object({
  id: z.number(),
  care_request_id: z.number(),
  patient_id: z.number(),
  status: OrderStatus,
  days: z.number().int(),
  currency: z.string(),
  subtotal_lkr: z.union([z.string(), z.number()]),
  total_lkr: z.union([z.string(), z.number()]),
  receipt_email_sent: z.boolean().optional(),
  receipt_sent_at: z.string().nullable().optional(),
  lines: z.array(OrderLineItem),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Order = z.infer<typeof Order>;

export const CheckoutCreate = z.object({
  care_request_id: z.number().int(),
  package_id: z.number().int(),
  addon_ids: z.array(z.number().int()).optional(),
  days: z.number().int().optional().nullable(),
});
export type CheckoutCreate = z.infer<typeof CheckoutCreate>;

export const PaymentIntentStatus = z.enum([
  'requires_payment',
  'processing',
  'succeeded',
  'failed',
  'cancelled',
]);
export type PaymentIntentStatus = z.infer<typeof PaymentIntentStatus>;

export const PaymentIntent = z.object({
  id: z.number(),
  order_id: z.number(),
  patient_id: z.number(),
  provider: z.enum(['mock', 'payhere']),
  status: PaymentIntentStatus,
  amount_lkr: z.union([z.string(), z.number()]),
  currency: z.string(),
  provider_intent_id: z.string(),
  idempotency_key: z.string(),
  client_payload: z.record(z.unknown()).optional().default({}),
  failure_code: z.string().optional().default(''),
  failure_message: z.string().optional().default(''),
  confirmed_at: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type PaymentIntent = z.infer<typeof PaymentIntent>;

export const ConditionTerm = z.object({
  slug: z.string(),
  canonical_en: z.string(),
  synonyms: z.record(z.array(z.string())).optional().default({}),
  active: z.boolean().optional(),
  version: z.number().optional(),
});
export type ConditionTerm = z.infer<typeof ConditionTerm>;

export const AdminConditionTerm = z.object({
  id: z.number(),
  slug: z.string(),
  canonical_en: z.string(),
  synonyms: z.record(z.array(z.string())).optional().default({}),
  active: z.boolean(),
  version: z.number(),
  notes: z.string().optional().default(''),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
});
export type AdminConditionTerm = z.infer<typeof AdminConditionTerm>;

export const AdminConditionListResponse = z.object({
  count: z.number(),
  results: z.array(AdminConditionTerm),
});
export type AdminConditionListResponse = z.infer<typeof AdminConditionListResponse>;

export type AdminConditionInput = {
  slug: string;
  canonical_en: string;
  synonyms?: Record<string, string[]>;
  active?: boolean;
  version?: number;
  notes?: string;
};

export const AnalyticsSeriesItem = z.object({
  key: z.string(),
  label: z.string(),
  count: z.number(),
});
export type AnalyticsSeriesItem = z.infer<typeof AnalyticsSeriesItem>;

export const AdminAnalytics = z.object({
  generated_at: z.string(),
  window_days: z.number(),
  requests_by_status: z.array(AnalyticsSeriesItem),
  roles: z.array(AnalyticsSeriesItem),
  match_latency: z.object({
    sample_size: z.number(),
    p50_ms: z.number().nullable(),
    p95_ms: z.number().nullable(),
    p99_ms: z.number().nullable(),
    avg_ms: z.number().nullable(),
    window_days: z.number(),
  }),
  relationships: z.object({
    active: z.number(),
    pending_payment: z.number(),
    ended: z.number(),
    by_status: z.array(AnalyticsSeriesItem),
  }),
});
export type AdminAnalytics = z.infer<typeof AdminAnalytics>;

export const AuditLog = z.object({
  id: z.number(),
  actor: z.number().nullable().optional(),
  actor_email: z.string().email().nullable().optional(),
  action: z.string(),
  ts: z.string(),
  ip: z.string().nullable().optional(),
  target_type: z.string().optional().default(''),
  target_id: z.string().optional().default(''),
  metadata: z.record(z.unknown()).optional().default({}),
});
export type AuditLog = z.infer<typeof AuditLog>;

export const AuditLogListResponse = z.object({
  count: z.number(),
  next: z.string().nullable().optional(),
  previous: z.string().nullable().optional(),
  results: z.array(AuditLog),
});
export type AuditLogListResponse = z.infer<typeof AuditLogListResponse>;

export type AuditLogListParams = {
  actor?: string;
  action?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
};

export const AUDIT_ACTIONS = [
  'view_health',
  'view_caregiver',
  'grant_consent',
  'revoke_consent',
  'login',
  'create_care_request',
  'cancel_care_request',
  'accept_care_request',
  'reject_care_request',
  'activate_care_relationship',
  'end_care_relationship',
  'create_order',
  'create_payment_intent',
  'confirm_payment',
  'payment_webhook',
  'receipt_sent',
  'create_medical_record',
  'update_medical_record',
  'delete_medical_record',
  'book_shift',
  'cancel_shift',
  'shift_conflict_fallback',
  'disable_user',
] as const;

export const ConditionListResponse = z.object({
  count: z.number(),
  results: z.array(ConditionTerm),
});
export type ConditionListResponse = z.infer<typeof ConditionListResponse>;

export const MedicalRecordAttachment = z.object({
  id: z.number(),
  record_id: z.number(),
  original_name: z.string(),
  content_type: z.string(),
  size_bytes: z.number(),
  uploaded_at: z.string(),
});
export type MedicalRecordAttachment = z.infer<typeof MedicalRecordAttachment>;

export const MedicalRecordList = z.object({
  id: z.number(),
  patient_id: z.number(),
  condition_slug: z.string(),
  condition_name: z.string(),
  title: z.string(),
  description: z.string().optional().default(''),
  recorded_at: z.string().nullable().optional(),
  attachment_count: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type MedicalRecordList = z.infer<typeof MedicalRecordList>;

export const MedicalRecordDetail = MedicalRecordList.extend({
  sensitive_notes: z.string().optional().default(''),
  attachments: z.array(MedicalRecordAttachment).optional().default([]),
});
export type MedicalRecordDetail = z.infer<typeof MedicalRecordDetail>;

export const MedicalRecordCreateInput = z.object({
  condition_slug: z.string(),
  title: z.string(),
  description: z.string().optional(),
  sensitive_notes: z.string().optional(),
  recorded_at: z.string().nullable().optional(),
  file: z.unknown().optional(),
});
export type MedicalRecordCreateInput = z.infer<typeof MedicalRecordCreateInput>;

export const MedicalRecordUpdateInput = z.object({
  condition_slug: z.string().optional(),
  title: z.string().optional(),
  description: z.string().optional(),
  sensitive_notes: z.string().optional(),
  recorded_at: z.string().nullable().optional(),
});
export type MedicalRecordUpdateInput = z.infer<typeof MedicalRecordUpdateInput>;

export const SignedDownloadUrl = z.object({
  attachment_id: z.number(),
  url: z.string(),
  expires_in: z.number(),
});
export type SignedDownloadUrl = z.infer<typeof SignedDownloadUrl>;

export const MessageThread = z.object({
  id: z.number(),
  relationship_id: z.number(),
  patient_id: z.number(),
  caregiver_id: z.number(),
  partner_label: z.string(),
  unread_count: z.number(),
  created_at: z.string(),
});
export type MessageThread = z.infer<typeof MessageThread>;

export const Message = z.object({
  id: z.number(),
  thread_id: z.number(),
  sender_id: z.number(),
  sender_role: z.string(),
  body: z.string(),
  created_at: z.string(),
  read_at: z.string().nullable().optional(),
  is_mine: z.boolean(),
});
export type Message = z.infer<typeof Message>;

export const MessageReadResult = z.object({
  thread_id: z.number(),
  last_read_message_id: z.number(),
  reader_id: z.number(),
  updated_count: z.number(),
});
export type MessageReadResult = z.infer<typeof MessageReadResult>;
