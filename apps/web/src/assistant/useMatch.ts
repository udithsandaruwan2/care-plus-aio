import { useCallback, useEffect, useRef } from 'react';
import type { MatchResponse } from '@care-plus/api-client';
import { AssistantState } from '@care-plus/core';
import { api } from '../auth/api';
import { getAccessToken } from '../auth/session';
import { useAuth } from '../auth/AuthContext';
import { useAssistant } from './store';
import { matchVoiceCopy } from './locale';
import { speakSerah, stopSpeaking } from './useTts';

let lastReadyRequestId: number | null = null;
let findingAnnounced = false;

function lastSerahLine(): string {
  const chat = useAssistant.getState().chat;
  for (let i = chat.length - 1; i >= 0; i--) {
    if (chat[i]?.role === 'serah') return chat[i]?.text ?? '';
  }
  return '';
}

function announceSerah(text: string, route: 'MATCH' | 'ACTION') {
  if (!text.trim()) return;
  if (lastSerahLine() === text) return;
  const store = useAssistant.getState();
  stopSpeaking();
  store.appendChat({ role: 'serah', text, route });
  void speakSerah(text, store.uiLanguage);
}

export function announceMatchFinding() {
  if (findingAnnounced) return;
  findingAnnounced = true;
  announceSerah(matchVoiceCopy(useAssistant.getState().uiLanguage).finding, 'MATCH');
}

export function announceMatchReady(requestId?: number) {
  if (requestId != null && lastReadyRequestId === requestId) return;
  if (requestId != null) lastReadyRequestId = requestId;
  findingAnnounced = false;
  announceSerah(matchVoiceCopy(useAssistant.getState().uiLanguage).resultsReady, 'ACTION');
}

export function resetMatchNarration() {
  lastReadyRequestId = null;
  findingAnnounced = false;
}

function wsBase(): string {
  const fromEnv = import.meta.env.VITE_WS_BASE_URL as string | undefined;
  if (fromEnv) return fromEnv.replace(/\/$/, '');
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  // Dev: Vite proxies /ws → backend :8000
  return `${proto}://${window.location.host}`;
}

/**
 * Keeps a JWT-authenticated WebSocket to ``ws/match/<user_id>/`` open while
 * the patient is on the home screen. Match payloads pushed from the API land
 * in the assistant store (and move FSM → RESULTS).
 */
export function useMatchSocket(opts?: {
  onCareRelationshipUpdated?: () => void;
  onEmergencyMatch?: (payload: MatchResponse) => void;
}) {
  const { user } = useAuth();
  const wsRef = useRef<WebSocket | null>(null);
  const onCareUpdated = opts?.onCareRelationshipUpdated;
  const onEmergencyMatch = opts?.onEmergencyMatch;

  useEffect(() => {
    if (!user?.id) return;
    const token = getAccessToken();
    if (!token) return;

    const url = `${wsBase()}/ws/match/${user.id}/?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string) as {
          type?: string;
          payload?: MatchResponse;
        };
        if (msg.type === 'match.results' && msg.payload) {
          const store = useAssistant.getState();
          store.setMatch(msg.payload);
          store.setMatching(false);
          if ((msg.payload as { emergency_context?: unknown }).emergency_context) {
            store.setState(AssistantState.EMERGENCY, { force: true });
            onEmergencyMatch?.(msg.payload);
          } else {
            store.setState(AssistantState.RESULTS, { force: true });
          }
          announceMatchReady(msg.payload.request_id);
        }
        if (msg.type === 'care_relationship.updated') {
          onCareUpdated?.();
        }
      } catch {
        /* ignore malformed frames */
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [user?.id, onCareUpdated, onEmergencyMatch]);
}

/** Runs VEHMF from the current intent. Used by the voice loop when chat promised a search. */
export async function runClientMatch(): Promise<boolean> {
  const store = useAssistant.getState();
  const { intent } = store;
  if (!intent.condition && !intent.language && !intent.care_level && !intent.raw_text) {
    return false;
  }

  store.setMatching(true);
  store.setState(AssistantState.MATCHING, { force: true });
  store.setMatchError(null);
  announceMatchFinding();
  try {
    const emergency = intent.urgency === 'urgent' || intent.urgency === 'critical';
    const result = await api.match({
      condition: intent.condition || intent.raw_text || 'general care',
      language: intent.language || 'English',
      care_level: intent.care_level || 'intermediate',
      query: intent.raw_text ?? '',
      k: 5,
      emergency,
    });
    store.setMatch(result);
    store.setMatching(false);
    store.setState(AssistantState.RESULTS, { force: true });
    announceMatchReady(result.request_id);
    return true;
  } catch (err) {
    store.setMatching(false);
    store.setMatchError(err instanceof Error ? err.message : 'Match failed.');
    store.setState(AssistantState.IDLE, { force: true });
    return false;
  }
}

/**
 * Runs VEHMF after intent is complete: SPEAKING → MATCHING → RESULTS.
 */
export function useMatch() {
  const runMatch = useCallback(async () => {
    await runClientMatch();
  }, []);

  return { runMatch };
}
