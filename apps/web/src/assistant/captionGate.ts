/**
 * Drop breath noises and low-confidence fragments before they become a turn.
 * A short unsure caption is an inhale. A longer phrase is kept even if the
 * browser is unsure, so a real sentence is not thrown away.
 */

const BREATH =
  /^(?:ah+|uh+|um+|hmm+|hm+|ha+|oh+|eh+|mm+|mhm+|a+|h+)[.!?…]*$/i;

export function acceptCaption(text: string, confidence?: number): boolean {
  const trimmed = text.trim();
  if (trimmed.length < 2) return false;
  if (BREATH.test(trimmed)) return false;
  const words = trimmed.split(/\s+/).length;
  if (confidence != null && Number.isFinite(confidence) && confidence < 0.45 && words < 3) {
    return false;
  }
  return true;
}
