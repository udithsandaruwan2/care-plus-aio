import { useCallback, useState } from 'react';
import { ApiError, AI_CONSENT_SCOPE, type VoiceLanguage } from '@care-plus/api-client';
import { AssistantState, nextMissingField, type IntentDraft } from '@care-plus/core';
import { api } from '../auth/api';
import { useAssistant } from './store';
import { speakSerah, stopSpeaking } from './useTts';

const CONSENT_STATUS = 451;

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
      setBusy(true);
      setError(null);
      store.setState(AssistantState.THINKING, { force: true });
      stopSpeaking();

      try {
        const result = await api.voiceTurn({
          text: opts.text,
          audio: opts.audio,
          hasPriorMatch: Boolean(store.match),
          priorIntent: store.intent as Record<string, unknown>,
          priorMatch: store.match as unknown as Record<string, unknown>,
          uiLanguage: store.uiLanguage,
        });
        setConsentNeeded(false);
        setAsrSource(result.asr_source);
        setAsrHeardLang(
          result.asr_language ||
            (result.intent?.language ? String(result.intent.language) : null),
        );
        setTtsSource(result.tts_source || null);
        setSerahReply(result.reply);

        if (result.transcript) {
          store.setTranscript(result.transcript);
          store.setInterim('');
        }

        if (result.session_id != null) {
          store.setSessionId(result.session_id);
        }

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
          store.setMatch(result.match);
          store.setState(AssistantState.RESULTS, { force: true });
        } else if (result.route === 'CLARIFY') {
          store.setState(AssistantState.CLARIFYING, { force: true });
        } else if (result.route === 'EMERGENCY') {
          store.setState(AssistantState.EMERGENCY, { force: true });
        } else if (result.route === 'ACTION' || result.route === 'CHAT') {
          // Keep RESULTS visible while chatting about / after matches.
          if (store.match && !result.clear_match) {
            store.setState(AssistantState.RESULTS, { force: true });
          } else if (result.intent && !nextMissingField(result.intent as IntentDraft)) {
            store.setState(AssistantState.SPEAKING, { force: true });
          } else {
            store.setState(AssistantState.IDLE, { force: true });
          }
        } else if (result.intent && !nextMissingField(result.intent as IntentDraft)) {
          store.setState(AssistantState.SPEAKING, { force: true });
        } else {
          store.setState(AssistantState.IDLE, { force: true });
        }

        await speakSerah(result.reply, result.reply_lang, {
          audioBase64: result.reply_audio_base64,
          audioMime: result.reply_audio_mime,
        });
        opts.continueListening?.();
      } catch (err) {
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
