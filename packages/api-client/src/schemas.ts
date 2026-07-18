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
