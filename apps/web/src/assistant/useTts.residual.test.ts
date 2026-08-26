import { describe, expect, it } from 'vitest';
import { estimateRemainingText } from './useTts';

describe('estimateRemainingText', () => {
  it('returns full text when nothing has played yet', () => {
    expect(estimateRemainingText('Hello there caregiver friend', 0)).toBe(
      'Hello there caregiver friend',
    );
  });

  it('returns empty when elapsed covers the utterance', () => {
    expect(estimateRemainingText('Short line', 60_000)).toBe('');
  });

  it('cuts near a word boundary for mid-utterance barge', () => {
    const text = 'One two three four five six seven eight nine ten';
    // ~14 chars/sec * 0.92 ≈ 12.9 → 1s ≈ 13 chars → around "One two three"
    const remaining = estimateRemainingText(text, 1000, 0.92);
    expect(remaining.length).toBeGreaterThan(0);
    expect(remaining.length).toBeLessThan(text.length);
    expect(remaining.startsWith(' ')).toBe(false);
  });
});
