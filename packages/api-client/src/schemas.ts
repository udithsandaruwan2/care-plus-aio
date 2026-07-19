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
});
export type MatchHit = z.infer<typeof MatchHit>;

export const MatchResponse = z.object({
  request_id: z.number(),
  latency_ms: z.number(),
  query: z.string(),
  emergency: z.boolean(),
  weights: MatchBreakdown,
  results: z.array(MatchHit),
});
export type MatchResponse = z.infer<typeof MatchResponse>;

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
