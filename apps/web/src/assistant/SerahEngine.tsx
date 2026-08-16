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
import { useMatchSocket } from './useMatch';
import { useAudioRecorder } from './useAudioRecorder';
import { useVoiceTurn } from './useVoiceTurn';
import { uiLanguageToRecognition } from './uiVoiceLanguage';
import { orbVisualState, type OrbVisualState } from './NeuralOrb';

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
    busy,
    error: turnError,
    consentNeeded,
    grantConsent,
    stopSpeaking,
  } = useVoiceTurn();
  useMatchSocket({
    onEmergencyMatch: (payload) => setEmergencyMatchId(payload.request_id),
  });

  const endingRef = useRef(false);
  const resumeListeningRef = useRef<() => Promise<void>>(async () => {});
  const consentBtnRef = useRef<HTMLButtonElement>(null);
  const busyRef = useRef(busy);
  busyRef.current = busy;

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
      setInterim(text);
    },
    onFinal: (text) => {
      appendTranscript(text);
    },
    onEnd: () => {
      if (endingRef.current) return;
      endingRef.current = true;
      void (async () => {
        mic.stop();
        const audio = await recorder.stop();
        const text = useAssistant.getState().transcript.trim();
        if (!text) {
          // Ambient silence — keep waiting, never send a fake "couldn't understand".
          endingRef.current = false;
          continueListening();
          return;
        }
        await beginTurn({ text, audio, source: 'voice' });
        endingRef.current = false;
      })();
    },
  });

  resumeListeningRef.current = async () => {
    endingRef.current = false;
    setInterim('');
    useAssistant.getState().setTranscript('');
    await mic.start();
    await recorder.start();
    speech.start();
    setState(AssistantState.LISTENING, { force: true });
  };

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
        stopSpeaking();
      }
      if (mic.active || speech.listening) {
        setConversationOn(false);
        speech.stop();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [mic.active, speech, busy, stopSpeaking]);

  const toggleMic = useCallback(async () => {
    if (listening) {
      setConversationOn(false);
      speech.stop();
      return;
    }
    if (busy) {
      stopSpeaking();
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
    stopSpeaking();
    await mic.start();
    await recorder.start();
    speech.start();
    setState(AssistantState.LISTENING, { force: true });
  }, [
    listening,
    busy,
    speech,
    stopSpeaking,
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
    stopSpeaking();
    setConversationOn(false);
    setSessionLive(false);
    setAsleep(false);
    try {
      await api.clearVoiceSession();
    } catch {
      // Still reset local state so the user can start fresh.
    } finally {
      reset();
      setSessionLive(false);
      setClearing(false);
    }
  }, [clearing, busy, listening, stopSpeaking, setSessionLive, setAsleep, reset]);

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
