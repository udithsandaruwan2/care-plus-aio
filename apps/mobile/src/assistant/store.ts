import { create } from 'zustand';
import { AssistantState, canTransition, type GoalField, type IntentDraft } from '@care-plus/core';
import type { MatchResponse } from '@care-plus/api-client';
import {
  loadUiVoiceLanguage,
  saveUiVoiceLanguage,
  type UiVoiceLanguage,
} from './uiVoiceLanguage';

export type ChatMessage = {
  id: string;
  role: 'user' | 'serah';
  text: string;
  route?: string;
};

const CHAT_LIMIT = 24;
let chatSeq = 0;

type AssistantStore = {
  state: AssistantState;
  intent: IntentDraft;
  transcript: string;
  interim: string;
  chat: ChatMessage[];
  match: MatchResponse | null;
  matchError: string | null;
  sessionId: number | null;
  uiLanguage: UiVoiceLanguage;
  matching: boolean;

  setState: (next: AssistantState, opts?: { force?: boolean }) => void;
  setIntentField: (field: GoalField | 'urgency', value: string) => void;
  setIntent: (draft: Partial<IntentDraft>) => void;
  setTranscript: (text: string) => void;
  setInterim: (text: string) => void;
  setMatch: (match: MatchResponse | null) => void;
  setMatchError: (msg: string | null) => void;
  appendChat: (msg: Omit<ChatMessage, 'id'>) => void;
  setSessionId: (id: number | null) => void;
  setUiLanguage: (lang: UiVoiceLanguage) => void;
  setMatching: (matching: boolean) => void;
  reset: () => void;
};

const initial = {
  state: AssistantState.IDLE as AssistantState,
  intent: {} as IntentDraft,
  transcript: '',
  interim: '',
  chat: [] as ChatMessage[],
  match: null as MatchResponse | null,
  matchError: null as string | null,
  sessionId: null as number | null,
  uiLanguage: loadUiVoiceLanguage(),
  matching: false,
};

export const useAssistant = create<AssistantStore>((set, get) => ({
  ...initial,

  setState: (next, opts) => {
    const { state } = get();
    if (opts?.force || state === next || canTransition(state, next)) {
      set({ state: next });
    } else if (__DEV__) {
      console.warn(`[assistant] blocked transition ${state} → ${next}`);
    }
  },

  setIntentField: (field, value) => set((s) => ({ intent: { ...s.intent, [field]: value } })),

  setIntent: (draft) => set((s) => ({ intent: { ...s.intent, ...draft } })),

  setTranscript: (text) => set({ transcript: text }),
  setInterim: (text) => set({ interim: text }),

  setMatch: (match) => set({ match, matchError: null }),
  setMatchError: (msg) => set({ matchError: msg }),
  appendChat: (msg) =>
    set((s) => ({
      chat: [...s.chat, { ...msg, id: `c${++chatSeq}` }].slice(-CHAT_LIMIT),
    })),
  setSessionId: (id) => set({ sessionId: id }),

  setUiLanguage: (lang) => {
    saveUiVoiceLanguage(lang);
    set({ uiLanguage: lang });
  },

  setMatching: (matching) => set({ matching }),

  reset: () =>
    set({
      ...initial,
      uiLanguage: get().uiLanguage,
    }),
}));
