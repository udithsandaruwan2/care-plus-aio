import { useCallback, useEffect, useRef } from 'react';
import type { MatchResponse } from '@care-plus/api-client';
import { AssistantState } from '@care-plus/core';
import { api } from '../auth/api';
import { getAccessToken } from '../auth/session';
import { useAuth } from '../auth/AuthContext';
import { useAssistant } from './store';

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
  if (!intent.condition) return false;

  store.setMatching(true);
  store.setState(AssistantState.MATCHING, { force: true });
  store.setMatchError(null);
  try {
    const emergency = intent.urgency === 'urgent' || intent.urgency === 'critical';
    const result = await api.match({
      condition: intent.condition,
      language: intent.language || 'English',
      care_level: intent.care_level || 'intermediate',
      query: intent.raw_text ?? '',
      k: 5,
      emergency,
    });
    store.setMatch(result);
    store.setMatching(false);
    store.setState(AssistantState.RESULTS, { force: true });
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
