import { describe, expect, it } from 'vitest';
import {
  shouldArmFallbackBargeMic,
  shouldListenAfterBarge,
  shouldPlayCutOffAfterBarge,
  shouldRearmFallbackMic,
  shouldReopenMicAfterSpeech,
  SPEAKER_TAIL_MS,
} from './speakerTail';

describe('shouldReopenMicAfterSpeech', () => {
  it('waits out her speaker tail and stays closed while Live is listening', () => {
    expect(SPEAKER_TAIL_MS).toBeGreaterThanOrEqual(400);
    expect(
      shouldReopenMicAfterSpeech({ conversationOn: true, busy: false, liveActive: false }),
    ).toBe(true);
    expect(
      shouldReopenMicAfterSpeech({ conversationOn: true, busy: false, liveActive: true }),
    ).toBe(false);
    expect(
      shouldReopenMicAfterSpeech({ conversationOn: true, busy: true, liveActive: false }),
    ).toBe(false);
    expect(
      shouldRearmFallbackMic({
        conversationOn: true,
        busy: false,
        liveActive: true,
        ending: false,
      }),
    ).toBe(false);
    expect(
      shouldRearmFallbackMic({
        conversationOn: true,
        busy: false,
        liveActive: false,
        ending: false,
      }),
    ).toBe(true);
    expect(shouldListenAfterBarge({ conversationOn: true, liveActive: false })).toBe(true);
    expect(shouldListenAfterBarge({ conversationOn: true, liveActive: true })).toBe(false);
    expect(shouldArmFallbackBargeMic(false)).toBe(true);
    expect(shouldArmFallbackBargeMic(true)).toBe(false);
    expect(shouldPlayCutOffAfterBarge(true)).toBe(false);
    expect(shouldPlayCutOffAfterBarge(false)).toBe(true);
  });
});
