import { create } from 'zustand';
import { AssistantState, canTransition, type GoalField, type IntentDraft } from '@care-plus/core';
import type { MatchHit, MatchResponse } from '@care-plus/api-client';
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

/** Booking funnel stage for voice navigation (drawer / accept / packages later). */
export type BookingStage =
  | 'idle'
  | 'profile'
  | 'requested'
  | 'awaiting_accept'
  | 'packages'
  | 'pay';

/** TTS depth when the Serah profile drawer opens. */
export type ProfileNarrateMode = 'brief' | 'detail';

const CHAT_LIMIT = 24;
let chatSeq = 0;

type AssistantStore = {
  state: AssistantState;
  intent: IntentDraft;
  /** Finalized transcript text. */
  transcript: string;
  /** In-flight (interim) transcript from ASR. */
  interim: string;
  /** Multi-turn chat bubbles (Step 15h). */
  chat: ChatMessage[];
  /** Latest VEHMF match payload (Step 20). */
  match: MatchResponse | null;
  /** Step 94 — match restored from IndexedDB rather than this session's network. */
  matchFromCache: boolean;
  matchStale: boolean;
  matchError: string | null;
  /** Server DialogueSession id (Step 15g). */
  sessionId: number | null;
  /** Locks captions, ASR, and Serah reply language. */
  uiLanguage: UiVoiceLanguage;
  /** VEHMF search in flight — show progress + skeleton cards. */
  matching: boolean;
  /** After goodbye: ignore utterances until a wake word. */
  asleep: boolean;
  /** User started a Serah session (mic or typed). Survives hub navigation. */
  sessionLive: boolean;
  /** Caregiver focused by voice (profile drawer). */
  focusedCaregiverId: number | null;
  /** Active care request created by voice (accept poll). */
  careRequestId: number | null;
  /** Voice booking funnel stage. */
  bookingStage: BookingStage;
  /** Pending drawer read-aloud; cleared after Serah speaks the summary. */
  profileNarrateMode: ProfileNarrateMode | null;

  setState: (next: AssistantState, opts?: { force?: boolean }) => void;
  setIntentField: (field: GoalField | 'urgency', value: string) => void;
  /** Merge a (partial) extracted draft over the current intent. */
  setIntent: (draft: Partial<IntentDraft>) => void;
  setTranscript: (text: string) => void;
  appendTranscript: (text: string) => void;
  setInterim: (text: string) => void;
  setMatch: (match: MatchResponse | null, opts?: { fromCache?: boolean; stale?: boolean }) => void;
  setMatchError: (msg: string | null) => void;
  appendChat: (msg: Omit<ChatMessage, 'id'>) => void;
  setSessionId: (id: number | null) => void;
  setUiLanguage: (lang: UiVoiceLanguage) => void;
  setMatching: (matching: boolean) => void;
  setAsleep: (asleep: boolean) => void;
  setSessionLive: (sessionLive: boolean) => void;
  setFocusedCaregiverId: (id: number | null) => void;
  setCareRequestId: (id: number | null) => void;
  setBookingStage: (stage: BookingStage) => void;
  setProfileNarrateMode: (mode: ProfileNarrateMode | null) => void;
  clearProfileNarrate: () => void;
  reset: () => void;
};

const initial = {
  state: AssistantState.IDLE as AssistantState,
  intent: {} as IntentDraft,
  transcript: '',
  interim: '',
  chat: [] as ChatMessage[],
  match: null as MatchResponse | null,
  matchFromCache: false,
  matchStale: false,
  matchError: null as string | null,
  sessionId: null as number | null,
  uiLanguage: loadUiVoiceLanguage(),
  matching: false,
  asleep: false,
  sessionLive: false,
  focusedCaregiverId: null as number | null,
  careRequestId: null as number | null,
  bookingStage: 'idle' as BookingStage,
  profileNarrateMode: null as ProfileNarrateMode | null,
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

  setMatch: (match, opts) =>
    set({
      match,
      matchError: null,
      matchFromCache: Boolean(opts?.fromCache),
      matchStale: Boolean(opts?.stale),
    }),
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
  setAsleep: (asleep) => set({ asleep }),
  setSessionLive: (sessionLive) => set({ sessionLive }),
  setFocusedCaregiverId: (id) => set({ focusedCaregiverId: id }),
  setCareRequestId: (id) => set({ careRequestId: id }),
  setBookingStage: (stage) => set({ bookingStage: stage }),
  setProfileNarrateMode: (mode) => set({ profileNarrateMode: mode }),
  clearProfileNarrate: () => set({ profileNarrateMode: null }),

  reset: () =>
    set({
      ...initial,
      uiLanguage: get().uiLanguage,
      sessionLive: get().sessionLive,
    }),
}));

export type { MatchHit, MatchResponse };
