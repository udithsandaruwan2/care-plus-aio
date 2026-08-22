/**
 * On-device CBF ranking fallback when offline (Step 98).
 * Uses HashEmbedder parity with Python + cached caregiver vectors.
 */

import type { MatchHit, MatchResponse } from '@care-plus/api-client';
import { isNetworkError, isTimeoutError } from '@care-plus/api-client';
import { dot, hashEmbed, intentToText, type IntentDraft } from '@care-plus/core';
import {
  type EdgeCaregiver,
  loadEdgeCaregiverCache,
  rememberEdgeCaregivers,
} from '../lib/query/caregiverEdgeCache';

export type EdgeDivergence = {
  at: string;
  provisionalIds: number[];
  serverIds: number[];
  overlap: number;
  provisionalTop?: number;
  serverTop?: number;
};

const DIVERGENCE_KEY = 'careplus:edge-match-divergence';

export function recordEdgeDivergence(div: EdgeDivergence): void {
  try {
    sessionStorage.setItem(DIVERGENCE_KEY, JSON.stringify(div));
  } catch {
    /* private mode */
  }
}

export function readLastEdgeDivergence(): EdgeDivergence | null {
  try {
    const raw = sessionStorage.getItem(DIVERGENCE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as EdgeDivergence;
  } catch {
    return null;
  }
}

export function compareEdgeRankings(
  provisional: MatchResponse | null,
  server: MatchResponse | null,
): EdgeDivergence | null {
  if (!provisional?.results?.length || !server?.results?.length) return null;
  const provisionalIds = provisional.results.map((r) => r.caregiver_id);
  const serverIds = server.results.map((r) => r.caregiver_id);
  const serverSet = new Set(serverIds);
  const overlap = provisionalIds.filter((id) => serverSet.has(id)).length;
  const div: EdgeDivergence = {
    at: new Date().toISOString(),
    provisionalIds,
    serverIds,
    overlap,
    provisionalTop: provisionalIds[0],
    serverTop: serverIds[0],
  };
  recordEdgeDivergence(div);
  return div;
}

export function shouldUseOfflineMatch(err?: unknown): boolean {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return true;
  if (err == null) return false;
  return isNetworkError(err) || isTimeoutError(err);
}

function explanationFor(cg: EdgeCaregiver, score: number): string {
  const bits = [
    cg.specialties.slice(0, 2).join(', ') || 'general care',
    cg.languages.slice(0, 2).join('/') || '',
    `on-device score ${score.toFixed(2)}`,
  ].filter(Boolean);
  return `Provisional match · ${bits.join(' · ')}`;
}

export function rankFromEdgeCache(
  intent: IntentDraft,
  caregivers: EdgeCaregiver[],
  opts?: { k?: number; emergency?: boolean },
): MatchResponse | null {
  const k = opts?.k ?? 5;
  const emergency = opts?.emergency ?? false;
  if (!caregivers.length) return null;
  const query = intentToText({
    condition: intent.condition || intent.raw_text || 'general care',
    language: intent.language || 'English',
    care_level: intent.care_level || 'intermediate',
    extra: intent.raw_text || '',
  });
  const [qVec] = hashEmbed([query]);
  if (!qVec) return null;

  const scored = caregivers
    .filter((c) => c.is_available !== false)
    .filter((c) => (c.display_name.match(/\p{L}/gu) || []).length >= 3 && c.specialties.length > 0)
    .map((c) => {
      const score = Math.max(0, dot(qVec, c.vector));
      return { c, score };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, k);

  if (!scored.length) return null;

  const results: MatchHit[] = scored.map(({ c, score }, i) => ({
    caregiver_id: c.id,
    rank: i + 1,
    score,
    breakdown: { cbf: score, cf: 0, geo: 0, trust: c.trust_score },
    explanation: explanationFor(c, score),
    display_name: c.display_name,
    specialties: c.specialties,
    languages: c.languages,
    care_levels: c.care_levels,
    trust_score: c.trust_score,
    is_available: c.is_available,
    was_exploratory: false,
  }));

  return {
    request_id: Date.now() % 1_000_000_000,
    latency_ms: 0,
    query,
    emergency,
    weights: { cbf: 1, cf: 0, geo: 0, trust: 0 },
    results,
    provisional: true,
    edge_source: 'on_device_hash',
    refined: false,
  };
}

export async function runOfflineMatch(
  intent: IntentDraft,
  opts?: { k?: number; emergency?: boolean },
): Promise<MatchResponse | null> {
  const cache = await loadEdgeCaregiverCache();
  if (!cache?.caregivers?.length) return null;
  return rankFromEdgeCache(intent, cache.caregivers, opts);
}

/** Warm the edge cache from a browse / match caregiver list. */
export async function warmEdgeCacheFromProfiles(
  profiles: Parameters<typeof rememberEdgeCaregivers>[0],
): Promise<void> {
  const usable = profiles.filter(
    (p) => (p.display_name.match(/\p{L}/gu) || []).length >= 3 && p.specialties.length > 0,
  );
  if (!usable.length) return;
  await rememberEdgeCaregivers(usable);
}

export function hitsToEdgeProfiles(
  hits: MatchHit[],
): Parameters<typeof rememberEdgeCaregivers>[0] {
  return hits.map((h) => ({
    id: h.caregiver_id,
    display_name: h.display_name,
    specialties: h.specialties,
    languages: h.languages,
    care_levels: h.care_levels,
    trust_score: h.trust_score ?? 0.5,
    is_available: h.is_available !== false,
  }));
}
