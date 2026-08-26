import { describe, expect, it } from 'vitest';
import { looksLikeCareSeek, looksLikeSearchPromise, shouldHoldMatchingUi } from '@care-plus/core';

describe('looksLikeCareSeek', () => {
  it('detects ASR-mangled hire + fever + Colombo care requests', () => {
    const line =
      "yeah suggest me best fight ever that currently I can higher in my area in Colombo 5 and also I have fever";
    expect(looksLikeCareSeek(line)).toBe(true);
  });

  it('detects explicit hire / caregiver language', () => {
    expect(looksLikeCareSeek('I want to hire a caregiver near me')).toBe(true);
  });

  it('does not treat a lone fever mention as a match request', () => {
    expect(looksLikeCareSeek('I think I have a fever today')).toBe(false);
  });
});

describe('looksLikeSearchPromise', () => {
  it('treats caregiver name listings as a search that must show cards', () => {
    const reply =
      'I can show you the available caregivers like Anjali Rajendran, Nimali Perera. Would you like to take a look at the first one?';
    expect(looksLikeSearchPromise(reply)).toBe(true);
  });
});

describe('shouldHoldMatchingUi', () => {
  it('holds matching UI when Serah lists available caregivers without a match payload', () => {
    expect(
      shouldHoldMatchingUi({
        seeking: false,
        route: 'CHAT',
        reply:
          'I can show you the available caregivers like Anjali Rajendran and Nimali Perera.',
        hasMatch: false,
        hasCondition: true,
      }),
    ).toBe(true);
  });
});
