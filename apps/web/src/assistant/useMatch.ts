import { useCallback, useEffect, useRef } from 'react';
import type { MatchInput, MatchResponse, VoiceTurnIntent } from '@care-plus/api-client';
import { AssistantState, type IntentDraft } from '@care-plus/core';
import { api } from '../auth/api';
import { getAccessToken, loadCachedUser } from '../auth/session';
import { persistLastMatch } from '../lib/query/matchCache';
import { useAuth } from '../auth/AuthContext';
import { useAssistant } from './store';
import { matchVoiceCopy } from './locale';
import { speakSerah, stopSpeaking } from './useTts';
import {
  claimTurnStage,
  lastStreamedReplyText,
  markTurnReplySpoken,
  rememberStreamedReply,
  type TurnStage,
} from './turnStream';
import {
  compareEdgeRankings,
  hitsToEdgeProfiles,
  runOfflineMatch,
  shouldUseOfflineMatch,
  warmEdgeCacheFromProfiles,
} from './offlineMatch';


function rememberMatch(match: MatchResponse | null) {
  const user = loadCachedUser();
  if (!user?.id) return;
  // The intent rides along so a restored match can be re-run against VEHMF.
  void persistLastMatch(user.id, match, useAssistant.getState().intent);
}

function hasIntent(intent: IntentDraft): boolean {
  return Boolean(intent.condition || intent.language || intent.care_level || intent.raw_text);
}

function matchPayload(intent: IntentDraft): MatchInput {
  return {
    condition: intent.condition || intent.raw_text || 'general care',
    language: intent.language || 'English',
    care_level: intent.care_level || 'intermediate',
    query: intent.raw_text ?? '',
    k: 5,
    emergency: intent.urgency === 'urgent' || intent.urgency === 'critical',
  };
}

let lastReadyRequestId: number | null = null;
let findingAnnounced = false;

function lastSerahLine(): string {
  const chat = useAssistant.getState().chat;
  for (let i = chat.length - 1; i >= 0; i--) {
    if (chat[i]?.role === 'serah') return chat[i]?.text ?? '';
  }
  return '';
}

function lastUserLine(): string {
  const chat = useAssistant.getState().chat;
  for (let i = chat.length - 1; i >= 0; i--) {
    if (chat[i]?.role === 'user') return chat[i]?.text ?? '';
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

function applyStreamIntent(intent: VoiceTurnIntent | Record<string, unknown>) {
  const store = useAssistant.getState();
  const draft: Partial<IntentDraft> = {};
  const raw = intent as VoiceTurnIntent;
  if (raw.raw_text) draft.raw_text = raw.raw_text;
  if (raw.condition) draft.condition = raw.condition;
  if (raw.language) draft.language = raw.language as IntentDraft['language'];
  if (raw.languages?.length) draft.languages = raw.languages as IntentDraft['languages'];
  if (raw.care_level) draft.care_level = raw.care_level as IntentDraft['care_level'];
  if (raw.urgency) draft.urgency = raw.urgency as IntentDraft['urgency'];
  if (Object.keys(draft).length) store.setIntent(draft);
}

type TurnPayload = {
  request_id?: string;
  stage?: string;
  transcript?: string;
  silent?: boolean;
  session_id?: number;
  intent?: VoiceTurnIntent | null;
  route?: string;
  situation?: string;
  clear_match?: boolean;
  reply?: string;
  reply_lang?: string;
  match?: MatchResponse | null;
  reply_audio_base64?: string;
  reply_audio_mime?: string;
};

function handleTurnMessage(type: string, payload: TurnPayload) {
  const stage = type.replace(/^turn\./, '') as TurnStage;
  const first = claimTurnStage(stage, payload.request_id);
  // Intent/route may be refined after salvage — always take the latest payload.
  if (!first && stage !== 'intent' && stage !== 'route') return;

  const store = useAssistant.getState();

  if (stage === 'transcript') {
    if (payload.silent) return;
    const text = (payload.transcript || '').trim();
    if (text) {
      store.setTranscript(text);
      store.setInterim('');
      if (lastUserLine() !== text) {
        store.appendChat({ role: 'user', text, route: payload.route });
      }
    }
    if (payload.session_id != null) store.setSessionId(payload.session_id);
    return;
  }

  if (stage === 'intent' && payload.intent) {
    applyStreamIntent(payload.intent);
    return;
  }

  if (stage === 'route') {
    if (payload.clear_match) store.setMatch(null);
    if (payload.session_id != null) store.setSessionId(payload.session_id);
    const route = payload.route || '';
    if (route === 'MATCH' || route === 'REFINE' || route === 'EMERGENCY') {
      store.setMatching(true);
      store.setState(AssistantState.MATCHING, { force: true });
    } else if (route === 'CLARIFY') {
      store.setMatching(false);
      store.setState(AssistantState.CLARIFYING, { force: true });
    }
    return;
  }

  if (stage === 'reply_text') {
    const reply = (payload.reply || '').trim();
    if (!reply) return;
    rememberStreamedReply(reply);
    if (lastSerahLine() !== reply) {
      store.appendChat({ role: 'serah', text: reply, route: payload.route });
    }
    if (
      store.state !== AssistantState.RESULTS &&
      store.state !== AssistantState.EMERGENCY &&
      store.state !== AssistantState.MATCHING
    ) {
      store.setState(AssistantState.CHAT_REPLY, { force: true });
    }
    return;
  }

  if (stage === 'match' && payload.match) {
    store.setMatch(payload.match);
    rememberMatch(payload.match);
    store.setMatching(false);
    if (
      payload.situation === 'emergency_match' ||
      (payload.match as { emergency?: boolean }).emergency
    ) {
      store.setState(AssistantState.EMERGENCY, { force: true });
    } else {
      store.setState(AssistantState.RESULTS, { force: true });
    }
    announceMatchReady(payload.match.request_id);
    return;
  }

  if (stage === 'reply_audio') {
    const reply = lastStreamedReplyText() || lastSerahLine();
    const audio = payload.reply_audio_base64 || '';
    if (!reply.trim()) return;
    markTurnReplySpoken(reply);
    void speakSerah(reply, payload.reply_lang || store.uiLanguage, {
      audioBase64: audio,
      audioMime: payload.reply_audio_mime || '',
    });
  }
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
          payload?: MatchResponse & TurnPayload;
        };
        if (msg.type?.startsWith('turn.') && msg.payload) {
          handleTurnMessage(msg.type, msg.payload);
          return;
        }
        if (msg.type === 'match.results' && msg.payload) {
          const store = useAssistant.getState();
          store.setMatch(msg.payload);
          rememberMatch(msg.payload);
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
  const emergency = intent.urgency === 'urgent' || intent.urgency === 'critical';

  const applyResult = (result: MatchResponse, opts?: { provisional?: boolean }) => {
    store.setMatch(result, opts?.provisional ? { fromCache: true, stale: true } : undefined);
    rememberMatch(result);
    store.setMatching(false);
    store.setState(AssistantState.RESULTS, { force: true });
    announceMatchReady(result.request_id);
  };

  try {
    if (shouldUseOfflineMatch()) {
      const offline = await runOfflineMatch(intent, { k: 5, emergency });
      if (offline) {
        applyResult(offline, { provisional: true });
        return true;
      }
    }
    const result = await api.match({
      condition: intent.condition || intent.raw_text || 'general care',
      language: intent.language || 'English',
      care_level: intent.care_level || 'intermediate',
      query: intent.raw_text ?? '',
      k: 5,
      emergency,
    });
    void warmEdgeCacheFromProfiles(hitsToEdgeProfiles(result.results));
    applyResult(result);
    return true;
  } catch (err) {
    if (shouldUseOfflineMatch(err)) {
      const offline = await runOfflineMatch(intent, { k: 5, emergency });
      if (offline) {
        applyResult(offline, { provisional: true });
        return true;
      }
    }
    store.setMatching(false);
    store.setMatchError(err instanceof Error ? err.message : 'Match failed.');
    store.setState(AssistantState.IDLE, { force: true });
    return false;
  }
}

/**
 * Silently re-run a match that was restored from IndexedDB so the panel shows
 * live VEHMF results instead of sitting behind a "may be out of date" badge.
 *
 * Bails out if the user has already moved on to a different match, and never
 * speaks or changes assistant state — this runs behind the visible UI.
 */
export async function refreshHydratedMatch(
  intent: IntentDraft,
  hydratedRequestId: number,
): Promise<boolean> {
  if (!hasIntent(intent)) return false;
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return false;

  try {
    const result = await api.match(matchPayload(intent));
    const store = useAssistant.getState();
    if (store.match?.request_id !== hydratedRequestId) return false;
    void warmEdgeCacheFromProfiles(hitsToEdgeProfiles(result.results));
    store.setMatch(result);
    rememberMatch(result);
    return true;
  } catch {
    return false;
  }
}

/**
 * When connectivity returns, replace a provisional on-device list with VEHMF
 * and record rank-id divergence (Step 98).
 */
export async function reconcileProvisionalMatch(): Promise<boolean> {
  const store = useAssistant.getState();
  const provisional = store.match;
  if (!provisional?.provisional) return false;
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return false;

  const { intent } = store;
  if (!intent.condition && !intent.language && !intent.care_level && !intent.raw_text) {
    return false;
  }

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
    compareEdgeRankings(provisional, result);
    void warmEdgeCacheFromProfiles(hitsToEdgeProfiles(result.results));
    store.setMatch(result);
    rememberMatch(result);
    store.setMatching(false);
    store.setState(AssistantState.RESULTS, { force: true });
    announceMatchReady(result.request_id);
    return true;
  } catch {
    return false;
  }
}

export function bindEdgeRankingLifecycle(): () => void {
  if (typeof window === 'undefined') return () => undefined;
  const onOnline = () => {
    void reconcileProvisionalMatch();
  };
  window.addEventListener('online', onOnline);
  return () => window.removeEventListener('online', onOnline);
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
