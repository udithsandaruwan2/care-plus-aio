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
