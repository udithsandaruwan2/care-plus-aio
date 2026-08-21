import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
  type RefObject,
} from 'react';
import { AssistantState, looksLikeWake, stripWakePrefix } from '@care-plus/core';
import { api } from '../auth/api';
import { useMicAmplitude } from '../neural-core/useMicAmplitude';
import { useAssistant } from './store';
import { useSpeechRecognition } from './useSpeechRecognition';
import { resetMatchNarration, useMatchSocket } from './useMatch';
import { useAudioRecorder } from './useAudioRecorder';
import { useVoiceTurn } from './useVoiceTurn';
import { uiLanguageToRecognition } from './uiVoiceLanguage';
import { orbVisualState, type OrbVisualState } from './NeuralOrb';
import { startBargeInWatch } from './bargeIn';
import { startEndOfUtteranceWatch } from './silenceWatch';
import { subscribeSerahSpeaking } from './useTts';
import type { TurnFailure } from './turnFailure';

type SerahEngineValue = {
  listening: boolean;
  busy: boolean;
  conversationOn: boolean;
  inputMode: 'voice' | 'text';
  setInputMode: (mode: 'voice' | 'text') => void;
  textInput: string;
  setTextInput: (value: string) => void;
  mic: ReturnType<typeof useMicAmplitude>;
  speech: ReturnType<typeof useSpeechRecognition>;
  turnError: string | null;
  turnFailure: TurnFailure | null;
  retryFailedTurn: () => Promise<void>;
  consentNeeded: boolean;
  emergencyMatchId: number | null;
  emergencyActive: boolean;
  visual: OrbVisualState;
  clearing: boolean;
  consentBtnRef: RefObject<HTMLButtonElement>;
  toggleMic: () => Promise<void>;
  onGrantConsent: () => Promise<void>;
  onNewRequest: () => Promise<void>;
  onTextSubmit: (e: FormEvent) => Promise<void>;
  submitText: (line: string) => Promise<void>;
};

const SerahEngineContext = createContext<SerahEngineValue | null>(null);

export function useSerahEngine(): SerahEngineValue {
  const ctx = useContext(SerahEngineContext);
  if (!ctx) {
    throw new Error('useSerahEngine must be used within SerahEngineProvider');
  }
  return ctx;
}

/**
 * Lives in AppShell so mic, speech, and VEHMF search survive hub navigation.
 */
export function SerahEngineProvider({ children }: { children: ReactNode }) {
  const [emergencyMatchId, setEmergencyMatchId] = useState<number | null>(null);
  const [conversationOn, setConversationOn] = useState(false);
  const [inputMode, setInputMode] = useState<'voice' | 'text'>('voice');
  const [textInput, setTextInput] = useState('');
  const [clearing, setClearing] = useState(false);
  const conversationOnRef = useRef(false);
  conversationOnRef.current = conversationOn;
  const pendingTextRef = useRef<string | null>(null);
  const mic = useMicAmplitude();
  const recorder = useAudioRecorder();
  const setState = useAssistant((s) => s.setState);
  const setInterim = useAssistant((s) => s.setInterim);
  const appendTranscript = useAssistant((s) => s.appendTranscript);
  const reset = useAssistant((s) => s.reset);
  const setSessionLive = useAssistant((s) => s.setSessionLive);
  const setAsleep = useAssistant((s) => s.setAsleep);
  const uiLanguage = useAssistant((s) => s.uiLanguage);
  const asrLang = uiLanguageToRecognition(uiLanguage);
  const {
    runTurn,
    retryFailedTurn,
    busy,
    error: turnError,
    failure: turnFailure,
    consentNeeded,
    grantConsent,
    stopSpeaking: stopTurnSpeaking,
  } = useVoiceTurn();
  useMatchSocket({
    onEmergencyMatch: (payload) => setEmergencyMatchId(payload.request_id),
  });

  const endingRef = useRef(false);
  const ignoreSpeechEndRef = useRef(false);
  const bargeStopRef = useRef<(() => void) | null>(null);
  const silenceStopRef = useRef<(() => void) | null>(null);
  const captionHeardRef = useRef(false);
  const emptyRearmCountRef = useRef(0);
  const rearmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bargedRef = useRef(false);
  const resumeListeningRef = useRef<() => Promise<void>>(async () => {});
  const armSilenceWatchRef = useRef<() => void>(() => {});
  const consentBtnRef = useRef<HTMLButtonElement>(null);
  const busyRef = useRef(busy);
  busyRef.current = busy;

  const clearRearmTimer = () => {
    if (rearmTimerRef.current) {
      clearTimeout(rearmTimerRef.current);
      rearmTimerRef.current = null;
    }
  };

  const continueListening = useCallback(() => {
    if (!conversationOnRef.current) return;
    void resumeListeningRef.current();
  }, []);

  const beginTurn = useCallback(
    async (opts: { text: string; audio: Blob | null; source: 'voice' | 'text' }) => {
      const store = useAssistant.getState();
      const text = opts.text.trim();
      if (!text) {
        continueListening();
        return;
      }

      if (store.asleep) {
        if (opts.source === 'voice' && !looksLikeWake(text)) {
          continueListening();
          return;
        }
        store.setAsleep(false);
        const rest = looksLikeWake(text) ? stripWakePrefix(text) : text;
        await runTurn({
          text: rest || 'hello',
          audio: opts.audio,
          continueListening,
        });
        return;
      }

      await runTurn({
        text,
        audio: opts.audio,
        continueListening,
      });
    },
    [continueListening, runTurn],
  );

  const speech = useSpeechRecognition({
    lang: asrLang,
    onInterim: (text) => {
      if (text.trim()) {
        captionHeardRef.current = true;
        emptyRearmCountRef.current = 0;
      }
      setInterim(text);
    },
    onFinal: (text) => {
      if (text.trim()) {
        captionHeardRef.current = true;
        emptyRearmCountRef.current = 0;
      }
      appendTranscript(text);
    },
    onEnd: () => {
      if (ignoreSpeechEndRef.current) {
        ignoreSpeechEndRef.current = false;
        return;
      }
      if (endingRef.current) return;
      endingRef.current = true;
      void (async () => {
        silenceStopRef.current?.();
        silenceStopRef.current = null;
        clearRearmTimer();
        const audio = await recorder.stop();
        // Keep the analyser up for a soft re-arm; only stop it when leaving voice mode.
        const text = useAssistant.getState().transcript.trim();
        if (!text) {
          endingRef.current = false;
          captionHeardRef.current = false;
          if (!conversationOnRef.current) {
            mic.stop();
            return;
          }
          emptyRearmCountRef.current += 1;
          // Ambient / no-speech churn — stop after a few empty cycles instead of looping forever.
          if (emptyRearmCountRef.current >= 3) {
            emptyRearmCountRef.current = 0;
            setConversationOn(false);
            mic.stop();
            const s = useAssistant.getState();
            if (s.match) setState(AssistantState.RESULTS, { force: true });
            else if (s.state === AssistantState.LISTENING) {
              setState(AssistantState.IDLE, { force: true });
            }
            return;
          }
          rearmTimerRef.current = setTimeout(() => {
            rearmTimerRef.current = null;
            if (!conversationOnRef.current || endingRef.current || busyRef.current) return;
            void (async () => {
              try {
                if (!mic.active) await mic.start();
                await recorder.start();
                speech.start();
                setState(AssistantState.LISTENING, { force: true });
                armSilenceWatchRef.current();
              } catch {
                /* mic permission / busy */
              }
            })();
          }, 700);
          return;
        }
        emptyRearmCountRef.current = 0;
        mic.stop();
        await beginTurn({ text, audio, source: 'voice' });
        endingRef.current = false;
      })();
    },
  });

  armSilenceWatchRef.current = () => {
    silenceStopRef.current?.();
    silenceStopRef.current = startEndOfUtteranceWatch({
      getAmplitude: () => mic.amplitudeRef.current,
      canEnd: () => captionHeardRef.current,
      onEnd: () => {
        silenceStopRef.current?.();
        silenceStopRef.current = null;
        if (!endingRef.current && conversationOnRef.current && captionHeardRef.current) {
          speech.stop();
        }
      },
    });
  };

  resumeListeningRef.current = async () => {
    bargeStopRef.current?.();
    bargeStopRef.current = null;
    silenceStopRef.current?.();
    silenceStopRef.current = null;
    clearRearmTimer();
    endingRef.current = false;
    captionHeardRef.current = false;
    emptyRearmCountRef.current = 0;
    setInterim('');
    useAssistant.getState().setTranscript('');
    await mic.start();
    await recorder.start();
    speech.start();
    setState(AssistantState.LISTENING, { force: true });
    armSilenceWatchRef.current();
  };

  // Step 85 — during Serah playback keep the analyser up, suppress ASR echo,
  // and barge-in when the user speaks over her.
  useEffect(() => {
    return subscribeSerahSpeaking((active) => {
      if (active) {
        bargedRef.current = false;
        bargeStopRef.current?.();
        bargeStopRef.current = null;
        silenceStopRef.current?.();
        silenceStopRef.current = null;
        void (async () => {
          if (speech.listening) {
            ignoreSpeechEndRef.current = true;
            speech.stop();
          }
          void recorder.stop();
          if (!mic.active) await mic.start();
          const s = useAssistant.getState().state;
          if (
            s !== AssistantState.RESULTS &&
            s !== AssistantState.EMERGENCY &&
            s !== AssistantState.MATCHING &&
            s !== AssistantState.LISTENING
          ) {
            setState(AssistantState.CHAT_REPLY, { force: true });
          }
          bargeStopRef.current = startBargeInWatch({
            getAmplitude: () => mic.amplitudeRef.current,
            onBargeIn: () => {
              if (bargedRef.current) return;
              bargedRef.current = true;
              bargeStopRef.current?.();
              bargeStopRef.current = null;
              stopTurnSpeaking();
              if (conversationOnRef.current) {
                void resumeListeningRef.current();
              }
            },
          });
        })();
        return;
      }

      bargeStopRef.current?.();
      bargeStopRef.current = null;
      if (bargedRef.current) {
        bargedRef.current = false;
        return;
      }
      if (conversationOnRef.current && !busyRef.current) {
        continueListening();
      }
    });
  }, [continueListening, mic, recorder, setState, speech, stopTurnSpeaking]);

  const listening = mic.active || speech.listening;
  const state = useAssistant((s) => s.state);
  const matching = useAssistant((s) => s.matching);
  const emergencyActive = state === AssistantState.EMERGENCY && emergencyMatchId != null;
  const visual = orbVisualState(state, listening, matching);

  useEffect(() => {
    if (consentNeeded) consentBtnRef.current?.focus();
  }, [consentNeeded]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== 'Escape') return;
      if (!(mic.active || speech.listening || busy)) return;
      e.preventDefault();
      if (busy) {
        stopTurnSpeaking();
      }
      if (mic.active || speech.listening) {
        setConversationOn(false);
        clearRearmTimer();
        silenceStopRef.current?.();
        silenceStopRef.current = null;
        speech.stop();
        mic.stop();
        void recorder.stop();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [mic.active, speech, busy, stopTurnSpeaking]);

  const toggleMic = useCallback(async () => {
    if (listening) {
      setConversationOn(false);
      clearRearmTimer();
      silenceStopRef.current?.();
      silenceStopRef.current = null;
      speech.stop();
      mic.stop();
      void recorder.stop();
      return;
    }
    if (busy) {
      stopTurnSpeaking();
      return;
    }

    const store = useAssistant.getState();
    const keepResults =
      store.asleep ||
      store.matching ||
      Boolean(store.match) ||
      store.state === AssistantState.CLARIFYING ||
      store.state === AssistantState.RESULTS ||
      store.state === AssistantState.CHAT_REPLY ||
      store.state === AssistantState.MATCHING ||
      store.state === AssistantState.LISTENING ||
      store.state === AssistantState.SPEAKING ||
      store.state === AssistantState.EMERGENCY;
    if (!keepResults) {
      reset();
    } else {
      setInterim('');
      store.setTranscript('');
    }
    setAsleep(false);
    setSessionLive(true);
    setConversationOn(true);
    endingRef.current = false;
    captionHeardRef.current = false;
    emptyRearmCountRef.current = 0;
    stopTurnSpeaking();
    clearRearmTimer();
    silenceStopRef.current?.();
    silenceStopRef.current = null;
    await mic.start();
    await recorder.start();
    speech.start();
    setState(AssistantState.LISTENING, { force: true });
    armSilenceWatchRef.current();
  }, [
    listening,
    busy,
    speech,
    stopTurnSpeaking,
    reset,
    setInterim,
    setAsleep,
    setSessionLive,
    mic,
    recorder,
    setState,
  ]);

  const onGrantConsent = useCallback(async () => {
    const ok = await grantConsent();
    if (ok) {
      await beginTurn({
        text: useAssistant.getState().transcript,
        audio: null,
        source: 'text',
      });
    }
  }, [grantConsent, beginTurn]);

  const onNewRequest = useCallback(async () => {
    if (clearing || busy || listening) return;
    setClearing(true);
    stopTurnSpeaking();
    setConversationOn(false);
    setSessionLive(false);
    setAsleep(false);
    try {
      await api.clearVoiceSession();
    } catch {
      // Still reset local state so the user can start fresh.
    } finally {
      reset();
      resetMatchNarration();
      setSessionLive(false);
      setClearing(false);
    }
  }, [clearing, busy, listening, stopTurnSpeaking, setSessionLive, setAsleep, reset]);

  const submitText = useCallback(
    async (line: string) => {
      const trimmed = line.trim();
      if (!trimmed || listening) return;
      setSessionLive(true);
      if (busyRef.current) {
        pendingTextRef.current = trimmed;
        return;
      }
      await beginTurn({ text: trimmed, audio: null, source: 'text' });
      const queued = pendingTextRef.current;
      if (queued) {
        pendingTextRef.current = null;
        await beginTurn({ text: queued, audio: null, source: 'text' });
      }
    },
    [listening, beginTurn, setSessionLive],
  );

  const onTextSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      const line = textInput.trim();
      if (!line) return;
      setTextInput('');
      await submitText(line);
    },
    [textInput, submitText],
  );

  const value = useMemo<SerahEngineValue>(
    () => ({
      listening,
      busy,
      conversationOn,
      inputMode,
      setInputMode,
      textInput,
      setTextInput,
      mic,
      speech,
      turnError,
      turnFailure,
      retryFailedTurn,
      consentNeeded,
      emergencyMatchId,
      emergencyActive,
      visual,
      clearing,
      consentBtnRef,
      toggleMic,
      onGrantConsent,
      onNewRequest,
      onTextSubmit,
      submitText,
    }),
    [
      listening,
      busy,
      conversationOn,
      inputMode,
      textInput,
      mic,
      speech,
      turnError,
      turnFailure,
      retryFailedTurn,
      consentNeeded,
      emergencyMatchId,
      emergencyActive,
      visual,
      clearing,
      toggleMic,
      onGrantConsent,
      onNewRequest,
      onTextSubmit,
      submitText,
    ],
  );

  return <SerahEngineContext.Provider value={value}>{children}</SerahEngineContext.Provider>;
}
