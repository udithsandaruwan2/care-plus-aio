import { describe, expect, it } from 'vitest';
import type { MatchHit } from '@care-plus/api-client';
import { comparativeMatchLine } from './compareMatch';

function hit(partial: Partial<MatchHit> & Pick<MatchHit, 'display_name' | 'breakdown' | 'score'>): MatchHit {
  return {
    caregiver_id: 1,
    rank: 1,
    specialties: [],
    languages: [],
    care_levels: [],
    explanation: '',
    is_available: true,
    ...partial,
  };
}

describe('comparativeMatchLine', () => {
  it('returns null without a second hit', () => {
    expect(
      comparativeMatchLine(
        hit({ display_name: 'A', score: 0.9, breakdown: { cbf: 0.9, cf: 0.4, geo: 0.5, trust: 0.7 } }),
        undefined,
      ),
    ).toBeNull();
  });

  it('names the strongest factor advantage', () => {
    const line = comparativeMatchLine(
      hit({
        display_name: 'Nimal',
        score: 0.91,
        breakdown: { cbf: 0.95, cf: 0.4, geo: 0.5, trust: 0.7 },
      }),
      hit({
        display_name: 'Kamal',
        score: 0.8,
        rank: 2,
        caregiver_id: 2,
        breakdown: { cbf: 0.5, cf: 0.4, geo: 0.5, trust: 0.7 },
      }),
    );
    expect(line).toContain('Kamal');
    expect(line).toContain('skills');
  });
});
