/** Bounded caregiver vector cache for on-device ranking (Step 98). */

import { hashEmbed, profileToText } from '@care-plus/core';
import type { CaregiverProfile } from '@care-plus/api-client';
import { readQuery, writeQuery } from './queryClient';
import { queryKeys, STALE_MS } from './keys';

export const EDGE_CACHE_MAX = 80;

export type EdgeCaregiver = {
  id: number;
  display_name: string;
  specialties: string[];
  languages: string[];
  care_levels: string[];
  trust_score: number;
  is_available: boolean;
  city?: string;
  vector: number[];
};

export type EdgeCachePayload = {
  updatedAt: number;
  caregivers: EdgeCaregiver[];
};

export function edgeCacheKey(): string {
  return queryKeys.edgeCaregiverVectors();
}

export async function loadEdgeCaregiverCache(): Promise<EdgeCachePayload | null> {
  const row = await readQuery<EdgeCachePayload>(edgeCacheKey());
  return row?.data ?? null;
}

/** Minimal profile fields needed to rebuild hash embeddings offline. */
export type EdgeProfileInput = Pick<
  CaregiverProfile,
  'id' | 'display_name' | 'specialties' | 'languages' | 'care_levels'
> &
  Partial<
    Pick<
      CaregiverProfile,
      'email' | 'certifications' | 'bio' | 'trust_score' | 'is_available' | 'city'
    >
  >;

export async function rememberEdgeCaregivers(
  profiles: EdgeProfileInput[],
): Promise<EdgeCachePayload> {
  const existing = (await loadEdgeCaregiverCache())?.caregivers ?? [];
  const byId = new Map<number, EdgeCaregiver>();
  for (const c of existing) byId.set(c.id, c);

  const texts = profiles.map((p) => profileToText(p));
  const vectors = hashEmbed(texts);
  profiles.forEach((p, i) => {
    byId.set(p.id, {
      id: p.id,
      display_name: p.display_name || p.email || `Caregiver ${p.id}`,
      specialties: p.specialties || [],
      languages: p.languages || [],
      care_levels: p.care_levels || [],
      trust_score: p.trust_score ?? 0.5,
      is_available: p.is_available !== false,
      city: p.city || undefined,
      vector: Array.from(vectors[i] ?? []),
    });
  });

  const merged = [...byId.values()]
    .sort((a, b) => b.trust_score - a.trust_score)
    .slice(0, EDGE_CACHE_MAX);
  const payload: EdgeCachePayload = { updatedAt: Date.now(), caregivers: merged };
  await writeQuery(edgeCacheKey(), payload);
  void STALE_MS.edgeVectors;
  return payload;
}
