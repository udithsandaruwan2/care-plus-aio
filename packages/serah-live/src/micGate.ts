/**
 * Decide whether a mic frame is speech worth sending to the live model.
 * Breaths and the assistant's own speaker bleed stay off the wire.
 * A loud frame while she is talking is a barge-in.
 */

export const MIC_GATE = {
  /** RMS below this is silence or an inhale, not a turn. */
  breathRms: 0.02,
  /** While the assistant is speaking, only a near-mouth level interrupts her. */
  bargeRms: 0.09,
} as const;

export type MicGateDecision = 'drop' | 'send' | 'barge';

export function frameRms(samples: ArrayLike<number>): number {
  const n = samples.length;
  if (!n) return 0;
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const s = samples[i] ?? 0;
    sum += s * s;
  }
  return Math.sqrt(sum / n);
}

export function decideMicFrame(rms: number, assistantSpeaking: boolean): MicGateDecision {
  if (!Number.isFinite(rms) || rms < 0) return 'drop';
  if (assistantSpeaking) {
    return rms >= MIC_GATE.bargeRms ? 'barge' : 'drop';
  }
  return rms >= MIC_GATE.breathRms ? 'send' : 'drop';
}
