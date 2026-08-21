import { describe, expect, it } from 'vitest';
import { EMBEDDING_DIM, HashEmbedder, hashEmbed, intentToText } from '@care-plus/core';
import fixtures from '../../../../packages/core/src/hash_embed_fixtures.json';

describe('HashEmbedder parity with Python (Step 98)', () => {
  it('matches fixture dim', () => {
    expect(fixtures.dim).toBe(EMBEDDING_DIM);
    expect(fixtures.blake2b_diabetes_hex).toBe('8673df823a2c62c3');
  });

  it('produces identical vectors for the shared fixture set', () => {
    const emb = new HashEmbedder();
    for (const row of fixtures.fixtures) {
      const [vec] = emb.embed([row.text]);
      expect(vec).toBeDefined();
      expect(vec!.length).toBe(EMBEDDING_DIM);
      const gold = row.vector;
      expect(gold.length).toBe(EMBEDDING_DIM);
      let maxDiff = 0;
      for (let i = 0; i < EMBEDDING_DIM; i++) {
        maxDiff = Math.max(maxDiff, Math.abs(vec![i]! - gold[i]!));
      }
      expect(maxDiff).toBeLessThan(1e-5);
    }
  });

  it('ranks shared-token caregiver text higher (smoke)', () => {
    const [q, a, b] = hashEmbed([
      'diabetes sinhala intermediate',
      'diabetes educator sinhala intermediate care',
      'wound care tamil basic only',
    ]);
    let qa = 0;
    let qb = 0;
    for (let i = 0; i < EMBEDDING_DIM; i++) {
      qa += q![i]! * a![i]!;
      qb += q![i]! * b![i]!;
    }
    expect(qa).toBeGreaterThan(qb);
  });

  it('intentToText matches Python join/lower', () => {
    expect(
      intentToText({
        condition: 'diabetes',
        language: 'Sinhala',
        care_level: 'intermediate',
      }),
    ).toBe('diabetes sinhala intermediate');
  });
});
