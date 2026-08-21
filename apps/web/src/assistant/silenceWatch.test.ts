import { describe, expect, it } from 'vitest';
import { END_OF_UTTERANCE_DEFAULTS, endOfUtteranceShouldFire } from './silenceWatch';

describe('endOfUtteranceShouldFire', () => {
  it('does not fire before speech was heard', () => {
    expect(
      endOfUtteranceShouldFire({
        heardSpeech: false,
        amplitude: 0.01,
        belowForMs: 2000,
      }),
    ).toBe(false);
  });

  it('does not fire while amplitude stays above silence floor', () => {
    expect(
      endOfUtteranceShouldFire({
        heardSpeech: true,
        amplitude: END_OF_UTTERANCE_DEFAULTS.silenceThreshold,
        belowForMs: 2000,
      }),
    ).toBe(false);
  });

  it('fires after sustained quiet following speech', () => {
    expect(
      endOfUtteranceShouldFire({
        heardSpeech: true,
        amplitude: 0.05,
        belowForMs: END_OF_UTTERANCE_DEFAULTS.silenceMs,
      }),
    ).toBe(true);
  });

  it('uses a higher speech threshold than ambient rumble', () => {
    expect(END_OF_UTTERANCE_DEFAULTS.speechThreshold).toBeGreaterThan(0.2);
  });
});
