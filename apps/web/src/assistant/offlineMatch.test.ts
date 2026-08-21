import { describe, expect, it } from 'vitest';
import { compareEdgeRankings, rankFromEdgeCache } from './offlineMatch';
import type { EdgeCaregiver } from '../lib/query/caregiverEdgeCache';
import { hashEmbed, profileToText } from '@care-plus/core';
import type { MatchResponse } from '@care-plus/api-client';

function cg(
  id: number,
  name: string,
  specialties: string[],
  languages: string[],
  care_levels: string[],
): EdgeCaregiver {
  const text = profileToText({
    display_name: name,
    specialties,
    languages,
    care_levels,
    certifications: [],
    bio: '',
  });
  const [vector] = hashEmbed([text]);
  return {
    id,
    display_name: name,
    specialties,
    languages,
    care_levels,
    trust_score: 0.8,
    is_available: true,
    vector: Array.from(vector!),
  };
}

describe('offlineMatch (Step 98)', () => {
  it('returns a provisional ranked list from cached vectors', () => {
    const caregivers = [
      cg(1, 'Diabetes CG', ['diabetes'], ['Sinhala'], ['intermediate']),
      cg(2, 'Wound CG', ['wound care'], ['Tamil'], ['basic']),
    ];
    const ranked = rankFromEdgeCache(
      { condition: 'diabetes', language: 'Sinhala', care_level: 'intermediate' },
      caregivers,
      { k: 2 },
    );
    expect(ranked).not.toBeNull();
    expect(ranked!.provisional).toBe(true);
    expect(ranked!.edge_source).toBe('on_device_hash');
    expect(ranked!.results[0]?.caregiver_id).toBe(1);
    expect(ranked!.results[0]?.score ?? 0).toBeGreaterThan(ranked!.results[1]?.score ?? 0);
  });

  it('records divergence between provisional and server ids', () => {
    const provisional = {
      results: [{ caregiver_id: 1 }, { caregiver_id: 2 }],
    } as MatchResponse;
    const server = {
      results: [{ caregiver_id: 2 }, { caregiver_id: 3 }],
    } as MatchResponse;
    const div = compareEdgeRankings(provisional, server);
    expect(div?.overlap).toBe(1);
    expect(div?.provisionalTop).toBe(1);
    expect(div?.serverTop).toBe(2);
  });
});
