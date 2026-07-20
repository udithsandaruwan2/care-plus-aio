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
        author: z.string().optional(),
      }),
    )
    .optional()
    .default([]),
  review_count: z.number().int().optional().default(0),
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

export const ConditionTerm = z.object({
  slug: z.string(),
  canonical_en: z.string(),
  synonyms: z.record(z.array(z.string())).optional().default({}),
  active: z.boolean().optional(),
  version: z.number().optional(),
});
export type ConditionTerm = z.infer<typeof ConditionTerm>;

export const ConditionListResponse = z.object({
  count: z.number(),
  results: z.array(ConditionTerm),
});
export type ConditionListResponse = z.infer<typeof ConditionListResponse>;
