import { describe, expect, it } from 'vitest';
import { acceptCaption } from './captionGate';

describe('acceptCaption', () => {
  it('drops an inhale and a one-letter fragment', () => {
    expect(acceptCaption('uhh')).toBe(false);
    expect(acceptCaption('h')).toBe(false);
    expect(acceptCaption('  ')).toBe(false);
  });

  it('drops a short caption the browser is unsure about', () => {
    expect(acceptCaption('the', 0.2)).toBe(false);
  });

  it('keeps a real request and a longer unsure sentence', () => {
    expect(acceptCaption('I need a nurse today', 0.9)).toBe(true);
    expect(acceptCaption('please find a caregiver near me', 0.3)).toBe(true);
  });
});
