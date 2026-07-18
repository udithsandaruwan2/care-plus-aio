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

/** First required field still missing (drives CLARIFYING prompts). */
export function nextMissingField(intent: IntentDraft): GoalField | null {
  return GOAL_FIELDS.find((f) => !intent[f]) ?? null;
}

/** Short status copy per state (English default; UI can localize later). */
export const STATE_COPY: Record<AssistantState, string> = {
  IDLE: 'Tap to speak',
  LISTENING: 'Listening…',
  THINKING: 'Understanding…',
  CLARIFYING: 'One more detail…',
  SPEAKING: 'Here’s what I heard',
  MATCHING: 'Finding your best match…',
  RESULTS: 'Matches ready',
  EMERGENCY: 'Health alert',
};

/** Allowed FSM transitions (docs/FRONTEND.md §4). */
export const TRANSITIONS: Record<AssistantState, AssistantState[]> = {
  IDLE: ['LISTENING', 'EMERGENCY'],
  LISTENING: ['LISTENING', 'THINKING', 'EMERGENCY', 'IDLE'],
  THINKING: ['SPEAKING', 'CLARIFYING', 'EMERGENCY'],
  CLARIFYING: ['LISTENING', 'EMERGENCY'],
  SPEAKING: ['MATCHING', 'IDLE'],
  MATCHING: ['RESULTS', 'EMERGENCY'],
  RESULTS: ['IDLE', 'EMERGENCY'],
  EMERGENCY: ['RESULTS', 'IDLE'],
};

export function canTransition(from: AssistantState, to: AssistantState): boolean {
  return TRANSITIONS[from].includes(to);
}

