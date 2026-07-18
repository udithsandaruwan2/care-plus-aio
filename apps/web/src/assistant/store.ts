import { create } from 'zustand';
import { AssistantState, canTransition, type GoalField, type IntentDraft } from '@care-plus/core';

type AssistantStore = {
  state: AssistantState;
  intent: IntentDraft;
  /** Finalized transcript text. */
  transcript: string;
  /** In-flight (interim) transcript from ASR. */
  interim: string;

  setState: (next: AssistantState, opts?: { force?: boolean }) => void;
  setIntentField: (field: GoalField | 'urgency', value: string) => void;
  setTranscript: (text: string) => void;
  appendTranscript: (text: string) => void;
  setInterim: (text: string) => void;
  reset: () => void;
};

const initial = {
  state: AssistantState.IDLE as AssistantState,
  intent: {} as IntentDraft,
  transcript: '',
  interim: '',
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

  setIntentField: (field, value) =>
    set((s) => ({ intent: { ...s.intent, [field]: value } })),

  setTranscript: (text) => set({ transcript: text }),
  appendTranscript: (text) =>
    set((s) => ({ transcript: (s.transcript + ' ' + text).trim(), interim: '' })),
  setInterim: (text) => set({ interim: text }),

  reset: () => set({ ...initial }),
}));
