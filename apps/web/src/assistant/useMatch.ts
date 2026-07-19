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
export function useMatchSocket() {
  const { user } = useAuth();
  const wsRef = useRef<WebSocket | null>(null);

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
          store.setState(AssistantState.RESULTS, { force: true });
        }
      } catch {
        /* ignore malformed frames */
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [user?.id]);
}

/**
 * Runs VEHMF after intent is complete: SPEAKING → MATCHING → RESULTS.
 */
export function useMatch() {
  const runMatch = useCallback(async () => {
    const store = useAssistant.getState();
    const { intent } = store;
    if (!intent.condition || !intent.language || !intent.care_level) return;

    store.setState(AssistantState.MATCHING, { force: true });
    store.setMatchError(null);
    try {
      const emergency = intent.urgency === 'urgent' || intent.urgency === 'critical';
      const result = await api.match({
        condition: intent.condition,
        language: intent.language,
        care_level: intent.care_level,
        query: intent.raw_text ?? '',
        k: 5,
        emergency,
      });
      store.setMatch(result);
      store.setState(AssistantState.RESULTS, { force: true });
    } catch (err) {
      store.setMatchError(err instanceof Error ? err.message : 'Match failed.');
      store.setState(AssistantState.IDLE, { force: true });
    }
  }, []);

  return { runMatch };
}
