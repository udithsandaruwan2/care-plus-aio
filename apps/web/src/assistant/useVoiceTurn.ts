import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ApiError,
  AI_CONSENT_SCOPE,
  isNetworkError,
  isTimeoutError,
  type VoiceLanguage,
} from '@care-plus/api-client';
import {
  AssistantState,
  looksLikeCareSeek,
  looksLikeSearchPromise,
  nextMissingField,
  shouldHoldMatchingUi,
  type IntentDraft,
} from '@care-plus/core';
import { api } from '../auth/api';
import { useConnectionStore } from '../auth/connectionStore';
import { useAssistant } from './store';
import { announceMatchFinding, announceMatchReady, runClientMatch } from './useMatch';
import { speakSerah, stopSpeaking } from './useTts';
import {
  httpNeedsTurnStage,
  resetTurnStream,
  turnReplyAlreadySpoken,
} from './turnStream';
import { classifyTurnFailure, type PendingTurn, type TurnFailure } from './turnFailure';

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

function preserveFailedUserLine(text: string) {
  const store = useAssistant.getState();
  const line = text.trim();
  if (!line) return;
  store.setTranscript(line);
  store.setInterim('');
  const lastUser = [...store.chat].reverse().find((m) => m.role === 'user');
  if (lastUser?.text !== line) {
    store.appendChat({ role: 'user', text: line });
  }
}

/**
 * Conversational turn: captions + audio → server ASR/router → Serah TTS + optional match.
 * Prefer progressive ``turn.*`` WebSocket stages when connected; HTTP remains the fallback.
 * Step 86: failed turns keep the transcript and can retry / auto-replay once online.
 */
export function useVoiceTurn() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [failure, setFailure] = useState<TurnFailure | null>(null);
  const [consentNeeded, setConsentNeeded] = useState(false);
  const [serahReply, setSerahReply] = useState<string | null>(null);
  const [asrSource, setAsrSource] = useState<string | null>(null);
  const [asrHeardLang, setAsrHeardLang] = useState<string | null>(null);
  const [ttsSource, setTtsSource] = useState<string | null>(null);

  const pendingRef = useRef<PendingTurn | null>(null);
  /** When true, the next transition to online replays ``pendingRef`` once. */
  const autoReplayRef = useRef(false);
  const continueListeningRef = useRef<(() => void) | undefined>(undefined);
  const busyRef = useRef(false);
  busyRef.current = busy;
  const runTurnRef = useRef<
    (opts: { text: string; audio: Blob | null; continueListening?: () => void }) => Promise<void>
  >(async () => undefined);

  const clearFailure = useCallback(() => {
    setFailure(null);
    setError(null);
    pendingRef.current = null;
    autoReplayRef.current = false;
  }, []);

  const runTurn = useCallback(
    async (opts: { text: string; audio: Blob | null; continueListening?: () => void }) => {
      const store = useAssistant.getState();
      const hasVisibleMatch = Boolean(store.match?.results?.length);
      const userLine = opts.text.trim();
      const seeking = looksLikeCareSeek(opts.text);
      resetTurnStream();
      setBusy(true);
      setError(null);
      setFailure(null);
      continueListeningRef.current = opts.continueListening;
      // Keep pending payload until success so retry/auto-replay can resubmit.
      pendingRef.current = { text: opts.text, audio: opts.audio };
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
        const rid = result.timings?.request_id || '';
        setConsentNeeded(false);
        clearFailure();
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

        if (httpNeedsTurnStage('transcript', rid) && result.transcript) {
          store.setTranscript(result.transcript);
          store.setInterim('');
        }

        if (result.session_id != null) {
          store.setSessionId(result.session_id);
        }

        const lineText = userLine || result.transcript?.trim() || '';
        if (lineText && httpNeedsTurnStage('transcript', rid)) {
          const chat = useAssistant.getState().chat;
          const lastUser = [...chat].reverse().find((m) => m.role === 'user');
          if (lastUser?.text !== lineText) {
            store.appendChat({ role: 'user', text: lineText, route: result.route });
          }
        }

        const stillSeeking =
          seeking ||
          looksLikeCareSeek(lineText) ||
          looksLikeCareSeek(result.transcript || '') ||
          looksLikeSearchPromise(result.reply || '');

        const needReplyText = httpNeedsTurnStage('reply_text', rid);
        const needMatch = httpNeedsTurnStage('match', rid);
        const outcome = applyTurnState(result, store, stillSeeking);
        const skipSearchNarration = outcome === 'hold' || outcome === 'matched';

        if (needReplyText && result.reply?.trim() && !skipSearchNarration) {
          const lastSerah = [...useAssistant.getState().chat]
            .reverse()
            .find((m) => m.role === 'serah');
          if (lastSerah?.text !== result.reply) {
            store.appendChat({ role: 'serah', text: result.reply, route: result.route });
          }
        }

        if (outcome === 'hold') {
          announceMatchFinding();
          void runClientMatch();
        }
        if (outcome === 'matched' && result.match && needMatch) {
          announceMatchReady(result.match.request_id);
        }

        if (result.reply?.trim() && result.situation !== 'goodbye' && !skipSearchNarration) {
          const current = useAssistant.getState().state;
          if (
            current !== AssistantState.RESULTS &&
            current !== AssistantState.EMERGENCY &&
            current !== AssistantState.MATCHING
          ) {
            store.setState(AssistantState.CHAT_REPLY, { force: true });
          }
        }

        // Unlock chat/mic; do not await TTS — listen cycle resumes via SerahEngine
        // when playback ends or barge-in fires (Step 85).
        setBusy(false);

        const needAudio = httpNeedsTurnStage('reply_audio', rid);
        const shouldSpeak =
          needAudio &&
          Boolean(result.reply?.trim()) &&
          !skipSearchNarration &&
          !turnReplyAlreadySpoken(result.reply);

        if (shouldSpeak) {
          let audioBase64 = result.reply_audio_base64;
          let audioMime = result.reply_audio_mime;
          if (result.audio_pending && !audioBase64) {
            try {
              const tts = await api.voiceTts({
                text: result.reply,
                replyLang: result.reply_lang,
              });
              audioBase64 = tts.reply_audio_base64;
              audioMime = tts.reply_audio_mime;
            } catch {
              /* browser TTS fallback inside speakSerah */
            }
          }
          // Fire-and-forget: barge-in / speak-end handler starts the next listen.
          void speakSerah(result.reply, result.reply_lang, {
            audioBase64,
            audioMime,
          });
        } else if (opts.continueListening) {
          opts.continueListening();
        }

        const after = useAssistant.getState();
        if (!shouldSpeak) {
          /* continueListening already called above when needed */
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
        preserveFailedUserLine(userLine || store.transcript);
        const classified = classifyTurnFailure(err);
        setFailure(classified);
        setError(classified.message);
        if (classified.kind === 'consent') {
          setConsentNeeded(true);
        }
        autoReplayRef.current = classified.autoReplay;
        if (isNetworkError(err) || isTimeoutError(err)) {
          useConnectionStore.getState().noteRequestOutcome(
            isTimeoutError(err) ? 'timeout' : 'network',
          );
        } else if (err instanceof ApiError) {
          useConnectionStore.getState().noteRequestOutcome('http');
        }
        store.setState(AssistantState.IDLE, { force: true });
      } finally {
        setBusy(false);
      }
    },
    [clearFailure],
  );

  runTurnRef.current = runTurn;

  const retryFailedTurn = useCallback(async () => {
    const pending = pendingRef.current;
    if (!pending || busyRef.current) return;
    // Manual retry claims the queue — online handler must not also fire.
    autoReplayRef.current = false;
    setFailure(null);
    setError(null);
    await runTurnRef.current({
      text: pending.text,
      audio: pending.audio,
      continueListening: continueListeningRef.current,
    });
  }, []);

  // Auto-replay once when the browser reports online again (Step 86).
  useEffect(() => {
    return useConnectionStore.subscribe((state, prev) => {
      if (state.browserOnline === prev.browserOnline) return;
      if (!state.browserOnline) return;
      if (!autoReplayRef.current) return;
      if (busyRef.current) return;
      const pending = pendingRef.current;
      if (!pending?.text.trim()) return;
      autoReplayRef.current = false;
      void runTurnRef.current({
        text: pending.text,
        audio: pending.audio,
        continueListening: continueListeningRef.current,
      });
    });
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

  return {
    runTurn,
    retryFailedTurn,
    clearFailure,
    busy,
    error,
    failure,
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
