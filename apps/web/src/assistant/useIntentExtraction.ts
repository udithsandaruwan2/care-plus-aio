import { useCallback, useState } from 'react';
import { ApiError, AI_CONSENT_SCOPE, type VoiceLanguage } from '@care-plus/api-client';
import { AssistantState, nextMissingField, type IntentDraft } from '@care-plus/core';
import { api } from '../auth/api';
import { useAssistant } from './store';
import type { RecognitionLang } from './useSpeechRecognition';

const LANG_HINT: Record<RecognitionLang, VoiceLanguage> = {
  'si-LK': 'Sinhala',
  'ta-LK': 'Tamil',
  'en-US': 'English',
};

const CONSENT_STATUS = 451;

/**
 * Sends a finalized transcript to the backend voice/intent endpoint, merges the
 * structured result into the assistant store, and drives the FSM to SPEAKING
 * (all required fields captured) or CLARIFYING (a field is still missing).
 *
 * The endpoint is consent-gated (HTTP 451): if AI consent is missing we surface
 * `consentNeeded` so the UI can offer a one-tap opt-in and retry.
 */
export function useIntentExtraction() {
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [consentNeeded, setConsentNeeded] = useState(false);

  const extract = useCallback(async (text: string, lang: RecognitionLang) => {
    const trimmed = text.trim();
    if (!trimmed) {
      // Nothing was heard — fall back to a re-prompt rather than a dead end.
      useAssistant.getState().setState(AssistantState.CLARIFYING, { force: true });
      return;
    }

    setExtracting(true);
    setError(null);
    const store = useAssistant.getState();
    store.setState(AssistantState.THINKING, { force: true });

    try {
      const result = await api.voiceIntent({ text: trimmed, language: LANG_HINT[lang] });
      setConsentNeeded(false);

      // Only overwrite fields the extractor actually filled — keeps prior chips
      // when the user answers a CLARIFYING follow-up with a short phrase.
      const draft: Partial<IntentDraft> = { raw_text: result.raw_text };
      if (result.condition) draft.condition = result.condition;
      if (result.language) draft.language = result.language;
      if (result.care_level) draft.care_level = result.care_level;
      if (result.urgency) draft.urgency = result.urgency;
      store.setIntent(draft);

      const missing = nextMissingField({ ...store.intent, ...draft });
      store.setState(missing ? AssistantState.CLARIFYING : AssistantState.SPEAKING, {
        force: true,
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === CONSENT_STATUS) {
        setConsentNeeded(true);
        setError('AI processing needs your consent before we can understand your request.');
      } else {
        setError(err instanceof Error ? err.message : 'Could not understand that. Try again.');
      }
      store.setState(AssistantState.IDLE, { force: true });
    } finally {
      setExtracting(false);
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

  return { extract, extracting, error, consentNeeded, grantConsent, setError };
}
