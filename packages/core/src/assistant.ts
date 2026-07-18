/** Assistant FSM states — Neural Core (docs/FRONTEND.md §4). */
export const AssistantState = {
  IDLE: 'IDLE',
  LISTENING: 'LISTENING',
  THINKING: 'THINKING',
  CLARIFYING: 'CLARIFYING',
  SPEAKING: 'SPEAKING',
  MATCHING: 'MATCHING',
  RESULTS: 'RESULTS',
  EMERGENCY: 'EMERGENCY',
} as const;

export type AssistantState = (typeof AssistantState)[keyof typeof AssistantState];

/** Intent fields that fill the Goal Ring. */
export const GOAL_FIELDS = ['condition', 'language', 'care_level'] as const;
export type GoalField = (typeof GOAL_FIELDS)[number];

export type IntentDraft = {
  condition?: string;
  language?: 'Sinhala' | 'Tamil' | 'English';
  care_level?: 'basic' | 'intermediate' | 'advanced';
  urgency?: 'routine' | 'urgent' | 'critical';
  raw_text?: string;
};

/** How many required Goal Ring segments are filled (0–1). */
export function goalRingProgress(intent: IntentDraft): number {
  const filled = GOAL_FIELDS.filter((f) => Boolean(intent[f])).length;
  return filled / GOAL_FIELDS.length;
}
