import { create } from 'zustand';
import { AssistantState, canTransition, type GoalField, type IntentDraft } from '@care-plus/core';
import type { MatchHit, MatchResponse } from '@care-plus/api-client';
import {
  loadUiVoiceLanguage,
  saveUiVoiceLanguage,
  type UiVoiceLanguage,
} from './uiVoiceLanguage';

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
  /** Server DialogueSession id (Step 15g). */
  sessionId: number | null;
  /** Locks captions, ASR, and Serah reply language. */
  uiLanguage: UiVoiceLanguage;

  setState: (next: AssistantState, opts?: { force?: boolean }) => void;
  setIntentField: (field: GoalField | 'urgency', value: string) => void;
  /** Merge a (partial) extracted draft over the current intent. */
  setIntent: (draft: Partial<IntentDraft>) => void;
  setTranscript: (text: string) => void;
  appendTranscript: (text: string) => void;
  setInterim: (text: string) => void;
  setMatch: (match: MatchResponse | null) => void;
  setMatchError: (msg: string | null) => void;
  setSessionId: (id: number | null) => void;
  setUiLanguage: (lang: UiVoiceLanguage) => void;
  reset: () => void;
};

const initial = {
  state: AssistantState.IDLE as AssistantState,
  intent: {} as IntentDraft,
  transcript: '',
  interim: '',
  match: null as MatchResponse | null,
  matchError: null as string | null,
  sessionId: null as number | null,
  uiLanguage: loadUiVoiceLanguage(),
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
  setSessionId: (id) => set({ sessionId: id }),

  setUiLanguage: (lang) => {
    saveUiVoiceLanguage(lang);
    set({ uiLanguage: lang });
  },

  reset: () =>
    set({
      ...initial,
      uiLanguage: get().uiLanguage,
    }),
}));

export type { MatchHit, MatchResponse };
