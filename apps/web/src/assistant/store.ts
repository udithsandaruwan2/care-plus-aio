import { create } from 'zustand';
import { AssistantState, canTransition, type GoalField, type IntentDraft } from '@care-plus/core';
import type { MatchHit, MatchResponse } from '@care-plus/api-client';

type AssistantStore = {
  state: AssistantState;
  intent: IntentDraft;
  /** Finalized transcript text. */
  transcript: string;
  /** In-flight (interim) transcript from ASR. */
  interim: string;
  /** Latest VEHMF match payload (Step 20). */
  match: MatchResponse | null;
  matchError: string | null;

  setState: (next: AssistantState, opts?: { force?: boolean }) => void;
  setIntentField: (field: GoalField | 'urgency', value: string) => void;
  /** Merge a (partial) extracted draft over the current intent. */
  setIntent: (draft: Partial<IntentDraft>) => void;
  setTranscript: (text: string) => void;
  appendTranscript: (text: string) => void;
  setInterim: (text: string) => void;
  setMatch: (match: MatchResponse | null) => void;
  setMatchError: (msg: string | null) => void;
  reset: () => void;
};

const initial = {
  state: AssistantState.IDLE as AssistantState,
  intent: {} as IntentDraft,
  transcript: '',
  interim: '',
  match: null as MatchResponse | null,
  matchError: null as string | null,
};

export const useAssistant = create<AssistantStore>((set, get) => ({
  ...initial,

  setState: (next, opts) => {
    const { state } = get();
    if (opts?.force || state === next || canTransition(state, next)) {
      set({ state: next });
    } else if (import.meta.env.DEV) {
      // Non-fatal in dev: log disallowed transition but allow forced stepping.
      console.warn(`[assistant] blocked transition ${state} → ${next}`);
    }
  },

  setIntentField: (field, value) => set((s) => ({ intent: { ...s.intent, [field]: value } })),

  setIntent: (draft) => set((s) => ({ intent: { ...s.intent, ...draft } })),

  setTranscript: (text) => set({ transcript: text }),
  appendTranscript: (text) =>
    set((s) => ({ transcript: (s.transcript + ' ' + text).trim(), interim: '' })),
  setInterim: (text) => set({ interim: text }),

  setMatch: (match) => set({ match, matchError: null }),
  setMatchError: (msg) => set({ matchError: msg }),

  reset: () => set({ ...initial }),
}));

export type { MatchHit, MatchResponse };
