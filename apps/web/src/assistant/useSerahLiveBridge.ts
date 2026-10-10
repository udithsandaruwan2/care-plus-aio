/**
 * Gemini Live bridge for the main Serah engine.
 * Falls back silently when the backend reports live.unavailable.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  createSerahLiveSession,
  type LiveMatchPayload,
  type LiveUiLanguage,
  type SerahLiveSession,
  acceptCaption,
  shouldRestartLive,
} from '@care-plus/serah-live';
import { AssistantState } from '@care-plus/core';
import { getAccessToken, loadCachedUser } from '../auth/session';
import { useAssistant } from './store';

const apiBase =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000/api/v1';
const wsBase = import.meta.env.VITE_WS_BASE_URL as string | undefined;

export function useSerahLiveBridge() {
  const [liveActive, setLiveActive] = useState(false);
  const [liveSpeaking, setLiveSpeaking] = useState(false);
  const [liveUnavailableReason, setLiveUnavailableReason] = useState<string | null>(null);
  const sessionRef = useRef<SerahLiveSession | null>(null);
  const startLiveRef = useRef<
    (opts?: { uiLanguage?: LiveUiLanguage; voice?: 'female' | 'male' }) => Promise<boolean>
  >(async () => false);
  const userStopRef = useRef(false);
  const replacingRef = useRef(false);
  const restartsRef = useRef(0);
  const epochRef = useRef(0);

  const applyMatch = useCallback((payload: LiveMatchPayload, cleared?: boolean) => {
    const store = useAssistant.getState();
    if (cleared || !payload) {
      store.setMatch(null);
      store.setMatching(false);
      return;
    }
    store.setMatch(payload as never);
    store.setMatching(false);
    store.setState(AssistantState.RESULTS, { force: true });
  }, []);

  useEffect(() => {
    const session = createSerahLiveSession({
      apiBaseUrl: apiBase,
      wsBaseUrl: wsBase,
      getAccessToken,
      getUserId: () => loadCachedUser()?.id ?? null,
      handlers: {
        onReady: () => {
          restartsRef.current = 0;
          setLiveActive(true);
          setLiveUnavailableReason(null);
        },
        onUnavailable: (reason) => {
          setLiveActive(false);
          setLiveUnavailableReason(reason);
        },
        onInputTranscript: (text, final) => {
          if (!acceptCaption(text)) return;
          const store = useAssistant.getState();
          if (final && text.trim()) {
            store.setInterim('');
            store.appendChat({ role: 'user', text: text.trim() });
            store.setTranscript(text.trim());
          } else {
            store.setInterim(text);
          }
        },
        onOutputTranscript: (text, final) => {
          const store = useAssistant.getState();
          if (!text.trim()) return;
          if (final) {
            store.appendChat({ role: 'assistant', text: text.trim() });
            store.setState(AssistantState.CHAT_REPLY, { force: true });
          }
        },
        onTool: (_name, status) => {
          const store = useAssistant.getState();
          if (status === 'running') {
            store.setState(AssistantState.THINKING, { force: true });
            store.setMatching(true);
          }
        },
        onMatch: applyMatch,
        onSpeaking: (speaking) => {
          setLiveSpeaking(speaking);
          const store = useAssistant.getState();
          if (speaking) {
            store.setState(AssistantState.SPEAKING, { force: true });
          } else if (store.match) {
            store.setState(AssistantState.RESULTS, { force: true });
          } else {
            store.setState(AssistantState.LISTENING, { force: true });
          }
        },
        onError: (message) => {
          setLiveUnavailableReason(message);
        },
        onClosed: () => {
          setLiveSpeaking(false);
          if (replacingRef.current) return;
          if (!shouldRestartLive(userStopRef.current, restartsRef.current)) {
            setLiveActive(false);
            return;
          }
          restartsRef.current += 1;
          replacingRef.current = true;
          void startLiveRef.current().finally(() => {
            replacingRef.current = false;
          });
        },
      },
    });
    sessionRef.current = session;
    return () => {
      session.stop();
      sessionRef.current = null;
    };
  }, [applyMatch]);

  const startLive = useCallback(
    async (opts?: { uiLanguage?: LiveUiLanguage; voice?: 'female' | 'male' }) => {
      const session = sessionRef.current;
      if (!session) return false;
      userStopRef.current = false;
      const epoch = ++epochRef.current;
      const store = useAssistant.getState();
      const ok = await session.start({
        uiLanguage: (opts?.uiLanguage || store.uiLanguage || 'English') as LiveUiLanguage,
        voice: opts?.voice || 'female',
      });
      if (epoch !== epochRef.current || userStopRef.current) {
        session.stop();
        return false;
      }
      setLiveActive(ok);
      if (!ok) return false;
      const micOk = await session.startMic();
      if (epoch !== epochRef.current || userStopRef.current) {
        session.stop();
        setLiveActive(false);
        return false;
      }
      if (!micOk) {
        session.stop();
        setLiveActive(false);
        setLiveUnavailableReason('Microphone unavailable for Live');
        return false;
      }
      store.setState(AssistantState.LISTENING, { force: true });
      return true;
    },
    [],
  );
  startLiveRef.current = startLive;

  const stopLive = useCallback(() => {
    userStopRef.current = true;
    epochRef.current += 1;
    replacingRef.current = false;
    sessionRef.current?.stopMic();
    sessionRef.current?.stop();
    setLiveActive(false);
    setLiveSpeaking(false);
  }, []);

  const sendLiveText = useCallback((text: string) => {
    if (!sessionRef.current?.ready) return false;
    sessionRef.current.sendText(text);
    return true;
  }, []);

  const interruptLive = useCallback(() => {
    sessionRef.current?.interrupt();
  }, []);

  return {
    liveActive,
    liveSpeaking,
    liveUnavailableReason,
    startLive,
    stopLive,
    sendLiveText,
    interruptLive,
  };
}
