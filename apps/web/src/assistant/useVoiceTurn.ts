import { useCallback, useState } from 'react';
import { ApiError, AI_CONSENT_SCOPE, type VoiceLanguage } from '@care-plus/api-client';
import {
  AssistantState,
  looksLikeCareSeek,
  looksLikeSearchPromise,
  nextMissingField,
  shouldHoldMatchingUi,
  type IntentDraft,
} from '@care-plus/core';
import { api } from '../auth/api';
import { useAssistant } from './store';
import { runClientMatch } from './useMatch';
import { speakSerah, stopSpeaking } from './useTts';

const CONSENT_STATUS = 451;

function applyTurnState(
  result: Awaited<ReturnType<typeof api.voiceTurn>>,
  store: ReturnType<typeof useAssistant.getState>,
  seeking: boolean,
): 'matched' | 'hold' | 'keep' | 'done' {
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

  if (result.situation === 'goodbye') {
    store.setAsleep(true);
    store.setMatching(false);
    store.setState(AssistantState.IDLE, { force: true });
    return 'done';
  }

  if (result.match) {
    store.setMatch(result.match);
    store.setMatching(false);
    store.setState(AssistantState.RESULTS, { force: true });
    return 'matched';
  }

  const intent = useAssistant.getState().intent;
  const hasCards = Boolean(store.match?.results?.length) && !result.clear_match;
  const searchInFlight = store.matching && !seeking && !result.clear_match && !hasCards;
  const hold = shouldHoldMatchingUi({
    seeking,
    route: result.route,
    situation: result.situation,
    reply: result.reply,
    hasMatch: hasCards,
    clearMatch: result.clear_match,
    hasCondition: Boolean(intent.condition),
    searchInFlight,
  });

  if (hold) {
    store.setMatching(true);
    store.setState(AssistantState.MATCHING, { force: true });
    return searchInFlight ? 'keep' : 'hold';
  }

  store.setMatching(false);

  if (
    (seeking || looksLikeSearchPromise(result.reply || '')) &&
    !intent.condition &&
    result.route !== 'CLARIFY'
  ) {
    store.setState(AssistantState.CLARIFYING, { force: true });
    return 'done';
  }

  if (result.route === 'CLARIFY') {
    store.setState(AssistantState.CLARIFYING, { force: true });
    return 'done';
  }
  if (result.route === 'EMERGENCY') {
    store.setState(AssistantState.EMERGENCY, { force: true });
    return 'done';
  }
  if (result.route === 'ACTION' || result.route === 'CHAT') {
    if (store.match && !result.clear_match) {
      store.setState(AssistantState.RESULTS, { force: true });
    } else {
      store.setState(AssistantState.CHAT_REPLY, { force: true });
    }
    return 'done';
  }
  if (result.intent && !nextMissingField(result.intent as IntentDraft)) {
    store.setState(AssistantState.SPEAKING, { force: true });
  } else {
    store.setState(AssistantState.IDLE, { force: true });
  }
  return 'done';
}

function isSilentTurn(result: Awaited<ReturnType<typeof api.voiceTurn>>): boolean {
  return Boolean(result.silent) || (result.situation === 'empty' && !result.reply?.trim());
}

/**
 * Conversational turn: captions + audio → server ASR/router → Serah TTS + optional match.
 */
export function useVoiceTurn() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [consentNeeded, setConsentNeeded] = useState(false);
  const [serahReply, setSerahReply] = useState<string | null>(null);
  const [asrSource, setAsrSource] = useState<string | null>(null);
  const [asrHeardLang, setAsrHeardLang] = useState<string | null>(null);
  const [ttsSource, setTtsSource] = useState<string | null>(null);

  const runTurn = useCallback(
    async (opts: { text: string; audio: Blob | null; continueListening?: () => void }) => {
      const store = useAssistant.getState();
      const hasVisibleMatch = Boolean(store.match?.results?.length);
      const userLine = opts.text.trim();
      const seeking = looksLikeCareSeek(opts.text);
      setBusy(true);
      setError(null);
      store.setSessionLive(true);
      if (seeking) {
        store.setMatching(true);
        store.setState(AssistantState.MATCHING, { force: true });
      } else {
        store.setState(AssistantState.THINKING, { force: true });
      }
      stopSpeaking();

      try {
        const result = await api.voiceTurn({
          text: opts.text,
          audio: opts.audio,
          hasPriorMatch: hasVisibleMatch,
          priorIntent: store.intent as Record<string, unknown>,
          priorMatch: hasVisibleMatch
            ? (store.match as unknown as Record<string, unknown>)
            : undefined,
          uiLanguage: store.uiLanguage,
        });
        setConsentNeeded(false);
        setAsrSource(result.asr_source);
        setAsrHeardLang(
          result.asr_language || (result.intent?.language ? String(result.intent.language) : null),
        );
        setTtsSource(result.tts_source || null);
        setSerahReply(result.reply);

        if (isSilentTurn(result)) {
          setBusy(false);
          if (opts.continueListening) opts.continueListening();
          return;
        }

        if (result.transcript) {
          store.setTranscript(result.transcript);
          store.setInterim('');
        }

        if (result.session_id != null) {
          store.setSessionId(result.session_id);
        }

        const lineText = userLine || result.transcript?.trim() || '';
        if (lineText) {
          store.appendChat({ role: 'user', text: lineText, route: result.route });
        }
        if (result.reply?.trim()) {
          store.appendChat({ role: 'serah', text: result.reply, route: result.route });
        }

        const stillSeeking =
          seeking ||
          looksLikeCareSeek(lineText) ||
          looksLikeCareSeek(result.transcript || '') ||
          looksLikeSearchPromise(result.reply || '');
        const outcome = applyTurnState(result, store, stillSeeking);
        if (outcome === 'hold') {
          void runClientMatch();
        }

        if (result.reply?.trim() && result.situation !== 'goodbye') {
          const current = useAssistant.getState().state;
          if (
            current !== AssistantState.RESULTS &&
            current !== AssistantState.EMERGENCY &&
            current !== AssistantState.MATCHING
          ) {
            store.setState(AssistantState.CHAT_REPLY, { force: true });
          }
        }

        // Unlock chat/mic while Serah speaks so matching cards stay usable.
        setBusy(false);

        if (result.reply?.trim()) {
          await speakSerah(result.reply, result.reply_lang, {
            audioBase64: result.reply_audio_base64,
            audioMime: result.reply_audio_mime,
          });
        }

        const after = useAssistant.getState();
        if (opts.continueListening) {
          opts.continueListening();
        } else if (after.match && (result.route === 'CHAT' || result.route === 'ACTION')) {
          after.setState(AssistantState.RESULTS, { force: true });
        } else if (after.state === AssistantState.CHAT_REPLY && after.match) {
          after.setState(AssistantState.RESULTS, { force: true });
        }
      } catch (err) {
        store.setMatching(false);
        setSerahReply(null);
        setAsrSource(null);
        setTtsSource(null);
        if (err instanceof ApiError && err.status === CONSENT_STATUS) {
          setConsentNeeded(true);
          setError('AI processing needs your consent before we can understand your request.');
        } else if (err instanceof ApiError && err.status === 401) {
          setError('Session expired — sign in again, then tap the mic.');
        } else {
          setError(err instanceof Error ? err.message : 'Could not understand that. Try again.');
        }
        store.setState(AssistantState.IDLE, { force: true });
      } finally {
        setBusy(false);
      }
    },
    [],
  );

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

  return {
    runTurn,
    busy,
    error,
    consentNeeded,
    grantConsent,
    serahReply,
    asrSource,
    asrHeardLang,
    ttsSource,
    setError,
    stopSpeaking,
  };
}
