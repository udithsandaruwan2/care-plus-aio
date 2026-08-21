/** Query keys + per-entity stale times (Step 94). */

export const STALE_MS = {
  profile: 5 * 60_000,
  browse: 2 * 60_000,
  caregiverDetail: 10 * 60_000,
  messageThread: 30_000,
  messages: 30_000,
  match: 30 * 60_000,
  edgeVectors: 24 * 60 * 60_000,
} as const;

export const queryKeys = {
  patientProfile: (userId: number | string) => `profile:patient:${userId}`,
  caregiverMe: (userId: number | string) => `profile:caregiver-me:${userId}`,
  browse: (filters: Record<string, string | boolean | undefined>) =>
    `browse:caregivers:${JSON.stringify(filters)}`,
  caregiverDetail: (id: number | string) => `caregiver:${id}`,
  messageThread: (userId: number | string) => `messages:thread:${userId}`,
  messages: (threadId: number | string) => `messages:list:${threadId}`,
  lastMatch: (userId: number | string) => `match:last:${userId}`,
  edgeCaregiverVectors: () => `edge:caregivers:vectors`,
} as const;
