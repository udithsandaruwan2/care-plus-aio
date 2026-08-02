import { useCallback, useState } from 'react';
import { ApiError, AI_CONSENT_SCOPE, type VoiceLanguage } from '@care-plus/api-client';
import { AssistantState, nextMissingField, type IntentDraft } from '@care-plus/core';
import { api } from '../api';
import { useAssistant } from './store';

const CONSENT_STATUS = 451;

function applyTurnState(
  result: Awaited<ReturnType<typeof api.voiceTurn>>,
  store: ReturnType<typeof useAssistant.getState>,
) {
  if (result.clear_match) {
    store.setMatch(null);
  }

  if (result.intent) {
    const draft: Partial<IntentDraft> = { raw_text: result.intent.raw_text };
    if (result.intent.condition) draft.condition = result.intent.condition;
    if (result.intent.language) {
      draft.language = result.intent.language as VoiceLanguage;
    }
    if (result.intent.languages?.length) {
      draft.languages = result.intent.languages as IntentDraft['languages'];
    }
    if (result.intent.care_level) {
      draft.care_level = result.intent.care_level as IntentDraft['care_level'];
    }
    if (result.intent.urgency) {
      draft.urgency = result.intent.urgency as IntentDraft['urgency'];
    }
    store.setIntent(draft);
  }

  if (result.match) {
    store.setState(AssistantState.MATCHING, { force: true });
    store.setMatch(result.match);
    store.setState(AssistantState.RESULTS, { force: true });
    return;
  }

  if (result.route === 'CLARIFY') {
    store.setState(AssistantState.CLARIFYING, { force: true });
    return;
  }
  if (result.route === 'EMERGENCY') {
    store.setState(AssistantState.EMERGENCY, { force: true });
    return;
  }
  if (result.route === 'ACTION' || result.route === 'CHAT') {
    if (store.match && !result.clear_match) {
      store.setState(AssistantState.RESULTS, { force: true });
    } else {
      store.setState(AssistantState.CHAT_REPLY, { force: true });
    }
    return;
  }
  if (result.intent && !nextMissingField(result.intent as IntentDraft)) {
    store.setState(AssistantState.SPEAKING, { force: true });
  } else {
    store.setState(AssistantState.IDLE, { force: true });
  }
}

/** Text-first conversational turn → /voice/turn/ (audio upload lands later). */
export function useVoiceTurn() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [consentNeeded, setConsentNeeded] = useState(false);

  const runTurn = useCallback(async (text: string) => {
    const store = useAssistant.getState();
    const hasVisibleMatch = Boolean(store.match?.results?.length);
    const userLine = text.trim();
    if (!userLine) return;

    setBusy(true);
    setError(null);
    store.setState(AssistantState.THINKING, { force: true });
    store.setTranscript(userLine);

    try {
      const result = await api.voiceTurn({
        text: userLine,
        hasPriorMatch: hasVisibleMatch,
        priorIntent: store.intent as Record<string, unknown>,
        priorMatch: hasVisibleMatch
          ? (store.match as unknown as Record<string, unknown>)
          : undefined,
        uiLanguage: store.uiLanguage,
      });
      setConsentNeeded(false);

      if (result.transcript) {
        store.setTranscript(result.transcript);
      }
      if (result.session_id != null) {
        store.setSessionId(result.session_id);
      }

      store.appendChat({
        role: 'user',
        text: userLine || result.transcript?.trim() || '',
        route: result.route,
      });
      if (result.reply?.trim()) {
        store.appendChat({ role: 'serah', text: result.reply, route: result.route });
      }

      applyTurnState(result, store);

      if (result.reply?.trim()) {
        const current = useAssistant.getState().state;
        if (
          current !== AssistantState.RESULTS &&
          current !== AssistantState.EMERGENCY &&
          current !== AssistantState.MATCHING
        ) {
          store.setState(AssistantState.CHAT_REPLY, { force: true });
        }
      }

      const after = useAssistant.getState();
      if (after.match && (result.route === 'CHAT' || result.route === 'ACTION')) {
        after.setState(AssistantState.RESULTS, { force: true });
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === CONSENT_STATUS) {
        setConsentNeeded(true);
        setError('AI processing needs your consent before we can understand your request.');
      } else if (err instanceof ApiError && err.status === 401) {
        setError('Session expired — sign in again.');
      } else {
        setError(err instanceof Error ? err.message : 'Could not understand that. Try again.');
      }
      store.setState(AssistantState.IDLE, { force: true });
    } finally {
      setBusy(false);
    }
  }, []);

  const grantConsent = useCallback(async () => {
    setError(null);
    try {
      await api.setConsent(AI_CONSENT_SCOPE, true);
      setConsentNeeded(false);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save consent.');
      return false;
    }
  }, []);

  return { runTurn, busy, error, consentNeeded, grantConsent, setError };
}
