import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AssistantState, goalRingProgress, nextMissingField } from '@care-plus/core';
import { useAuth } from '../auth/AuthContext';
import { useCaregiverProfile } from '../auth/useCaregiverProfile';
import { usePatientProfile } from '../auth/usePatientProfile';
import { api } from '../auth/api';
import { useMicAmplitude } from '../neural-core/useMicAmplitude';
import { useAssistant } from '../assistant/store';
import { useReducedMotion } from '../assistant/useReducedMotion';
import { GoalRing } from '../assistant/GoalRing';
import { ChatBubbles } from '../assistant/ChatBubbles';
import { EntityChips } from '../assistant/EntityChips';
import { Transcript } from '../assistant/Transcript';
import { StateStepper } from '../assistant/StateStepper';
import { useSpeechRecognition } from '../assistant/useSpeechRecognition';
import { MatchResultCards } from '../assistant/MatchResultCards';
import { useMatchSocket } from '../assistant/useMatch';
import { useAudioRecorder } from '../assistant/useAudioRecorder';
import { useVoiceTurn } from '../assistant/useVoiceTurn';
import { LanguagePicker } from '../assistant/LanguagePicker';
import { stateCopy } from '../assistant/locale';
import { uiLanguageToRecognition } from '../assistant/uiVoiceLanguage';
import { PageHeader } from '../components/ui/PageHeader';

const CLARIFY_PROMPTS: Record<string, string> = {
  condition: 'What condition or symptom should I focus on?',
  language: 'Which language do you prefer for care?',
  care_level: 'How much support do you need — basic, intermediate, or advanced?',
};

const NeuralCoreCanvas = lazy(() =>
  import('../neural-core/NeuralCoreCanvas').then((m) => ({ default: m.NeuralCoreCanvas })),
);

export function HomePage() {
  const { user } = useAuth();
  const { canRequestCare, completionPercent } = usePatientProfile();
  const { isMatchEligible, completionPercent: cgCompletion } = useCaregiverProfile();
  const [emergencyMatchId, setEmergencyMatchId] = useState<number | null>(null);
  const [conversationOn, setConversationOn] = useState(false);
  const conversationOnRef = useRef(false);
  conversationOnRef.current = conversationOn;
  const mic = useMicAmplitude();
  const reducedMotion = useReducedMotion();
  const recorder = useAudioRecorder();
  const {
    state,
    intent,
    transcript,
    interim,
    match,
    chat,
    uiLanguage,
    setState,
    setInterim,
    appendTranscript,
    setUiLanguage,
    reset,
  } = useAssistant();
  const asrLang = uiLanguageToRecognition(uiLanguage);
  const {
    runTurn,
    busy,
    error: turnError,
    consentNeeded,
    grantConsent,
    stopSpeaking,
  } = useVoiceTurn();
  useMatchSocket({
    onEmergencyMatch: (payload) => setEmergencyMatchId(payload.request_id),
  });

  const endingRef = useRef(false);
  const resumeListeningRef = useRef<() => Promise<void>>(async () => {});
  const consentBtnRef = useRef<HTMLButtonElement>(null);
  const [clearing, setClearing] = useState(false);

  const speech = useSpeechRecognition({
    lang: asrLang,
    onInterim: (text) => {
      setInterim(text);
    },
    onFinal: (text) => {
      appendTranscript(text);
    },
    onEnd: () => {
      if (endingRef.current) return;
      endingRef.current = true;
      void (async () => {
        mic.stop();
        const audio = await recorder.stop();
        const text = useAssistant.getState().transcript;
        await runTurn({
          text,
          audio,
          continueListening: () => {
            if (!conversationOnRef.current) return;
            void resumeListeningRef.current();
          },
        });
        endingRef.current = false;
      })();
    },
  });

  resumeListeningRef.current = async () => {
    endingRef.current = false;
    setInterim('');
    useAssistant.getState().setTranscript('');
    await mic.start();
    await recorder.start();
    speech.start();
    setState(AssistantState.LISTENING, { force: true });
  };

  const listening = mic.active || speech.listening;
  const emergencyActive = state === AssistantState.EMERGENCY && emergencyMatchId != null;

  useEffect(() => {
    if (consentNeeded) consentBtnRef.current?.focus();
  }, [consentNeeded]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== 'Escape') return;
      if (!(mic.active || speech.listening || busy)) return;
      e.preventDefault();
      if (busy) {
        setConversationOn(false);
        stopSpeaking();
      }
      speech.stop();
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [mic.active, speech, busy, stopSpeaking]);

  async function toggleMic() {
    if (listening || busy) {
      if (busy) {
        setConversationOn(false);
        stopSpeaking();
      }
      speech.stop();
      return;
    }

    const current = useAssistant.getState().state;
    if (
      current !== AssistantState.CLARIFYING &&
      current !== AssistantState.RESULTS &&
      current !== AssistantState.CHAT_REPLY
    ) {
      reset();
    } else {
      setInterim('');
      useAssistant.getState().setTranscript('');
    }
    setConversationOn(true);
    endingRef.current = false;
    await mic.start();
    await recorder.start();
    speech.start();
    setState(AssistantState.LISTENING, { force: true });
  }

  async function onGrantConsent() {
    const ok = await grantConsent();
    if (ok) {
      await runTurn({ text: useAssistant.getState().transcript, audio: null });
    }
  }

  async function onNewRequest() {
    if (clearing || busy || listening) return;
    setClearing(true);
    stopSpeaking();
    setConversationOn(false);
    try {
      await api.clearVoiceSession();
    } catch {
      // Still reset local state so the user can start fresh.
    } finally {
      reset();
      setClearing(false);
    }
  }

  const progress = Math.round(goalRingProgress(intent) * 100);
  const missingField = nextMissingField(intent);
  const clarifyPrompt =
    state === AssistantState.CLARIFYING && missingField ? CLARIFY_PROMPTS[missingField] : null;

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col">
      <PageHeader
        eyebrow="Assistant"
        title="Talk with Serah"
        subtitle="Choose Sinhala, Tamil, or English, then speak. Serah replies in that language and ranks caregivers when you need care."
        actions={
          <Link
            to="/platform"
            className="rounded-full border border-hair px-3 py-1.5 text-xs text-muted hover:border-cyan hover:text-cyan"
          >
            Manage care →
          </Link>
        }
      />

      <div className="mt-4">
        <LanguagePicker value={uiLanguage} onChange={setUiLanguage} disabled={listening || busy} />
      </div>

      <div className="mx-auto mt-3 flex w-full max-w-xl flex-wrap justify-center gap-2 text-xs">
        {user?.role === 'patient' && !canRequestCare && (
          <Link
            to="/onboarding"
            className="rounded-full border border-amber/40 px-3 py-1 text-amber transition hover:bg-amber/10"
          >
            Complete profile ({completionPercent}%)
          </Link>
        )}
        {user?.role === 'caregiver' && !isMatchEligible && (
          <Link
            to="/caregiver-onboarding"
            className="rounded-full border border-amber/40 px-3 py-1 text-amber transition hover:bg-amber/10"
          >
            Complete caregiver profile ({cgCompletion}%)
          </Link>
        )}
      </div>

      <section className="relative mx-auto mt-4 flex w-full max-w-lg flex-col items-center">
        {emergencyActive && (
          <div className="mb-3 w-full rounded-2xl border border-rose/50 bg-rose/10 p-4 text-left backdrop-blur">
            <p className="font-display text-sm tracking-wide text-rose">EMERGENCY alert</p>
            <p className="mt-1 text-xs text-muted">
              Serah detected a critical health signal and pushed your nearest advanced caregiver.
            </p>
            <a
              href="#emergency-match"
              className="mt-3 inline-block rounded-full border border-rose/40 px-3 py-1.5 text-xs text-rose transition hover:bg-rose/10"
            >
              View emergency match
            </a>
          </div>
        )}
        <button
          type="button"
          onClick={toggleMic}
          aria-pressed={listening}
          aria-label={listening ? 'Stop listening' : 'Tap to speak'}
          className="cursor-pointer rounded-full border-0 bg-transparent p-0 outline-none focus-visible:ring-2 focus-visible:ring-cyan"
        >
          <GoalRing intent={intent} size={288}>
            <Suspense
              fallback={
                <div className="flex h-full items-center justify-center text-sm text-muted">
                  Loading assistant…
                </div>
              }
            >
              <NeuralCoreCanvas
                amplitude={mic.amplitude}
                state={state}
                reducedMotion={reducedMotion}
                className="pointer-events-none h-full w-full"
              />
            </Suspense>
          </GoalRing>
        </button>

          <p className="mt-2 font-display text-sm tracking-wide text-cyan" aria-live="polite">
            {stateCopy(state, uiLanguage)}
          </p>
          <ChatBubbles messages={chat} />
          {clarifyPrompt && (
            <p className="mt-1 text-sm text-amber" aria-live="polite">
              {clarifyPrompt} Keep talking — your other details stay.
            </p>
          )}
          {(mic.error || speech.error) && (
            <p className="mt-1 text-sm text-rose" role="alert">
              {mic.error ?? speech.error}
            </p>
          )}
          {turnError && !consentNeeded && (
            <p className="mt-1 text-sm text-rose" role="alert">
              {turnError}
            </p>
          )}
          {consentNeeded && (
            <div
              className="mt-3 w-full max-w-sm rounded-xl border border-amber/40 bg-amber/5 p-4 text-center"
              role="alertdialog"
              aria-labelledby="consent-title"
            >
              <p id="consent-title" className="text-sm text-amber">
                {turnError}
              </p>
              <button
                ref={consentBtnRef}
                type="button"
                onClick={onGrantConsent}
                className="mt-3 rounded-full bg-amber/90 px-5 py-2 text-sm font-medium text-void transition hover:bg-amber focus-visible:ring-2 focus-visible:ring-cyan"
              >
                Enable AI processing
              </button>
            </div>
          )}
          {!speech.supported && (
            <p className="mt-1 text-xs text-amber" role="status">
              Live captions unsupported here — audio still uploads for Serah (try Chrome/Edge).
            </p>
          )}
          <p className="mt-1 text-xs text-muted" aria-live="polite">
            Goal {progress}% · level {(mic.amplitude * 100).toFixed(0)}%
          </p>

          <Transcript transcript={transcript} interim={interim} />
          <div className="mt-3">
            <EntityChips intent={intent} uiLanguage={uiLanguage} />
          </div>

          {match &&
            (state === AssistantState.RESULTS ||
              state === AssistantState.MATCHING ||
              state === AssistantState.EMERGENCY) && (
              <MatchResultCards
                id={emergencyActive ? 'emergency-match' : undefined}
                match={match}
                canRequestCare={canRequestCare}
                uiLanguage={uiLanguage}
              />
          )}

          <button
            type="button"
            onClick={toggleMic}
            disabled={busy && !listening}
            aria-pressed={listening}
            aria-label={
              listening
                ? 'Stop listening and send'
                : busy
                  ? 'Serah is speaking'
                  : 'Tap to speak with Serah'
            }
            className={`mt-4 rounded-full px-6 py-2.5 text-sm font-medium transition focus-visible:ring-2 focus-visible:ring-cyan disabled:opacity-50 ${
              listening
                ? 'bg-rose/20 text-rose ring-1 ring-rose/50'
                : 'bg-cyan/90 text-void hover:bg-cyan'
            }`}
          >
            {listening
              ? 'Stop / send'
              : busy
                ? 'Serah is speaking…'
                : state === AssistantState.CLARIFYING ||
                    state === AssistantState.RESULTS ||
                    state === AssistantState.EMERGENCY ||
                    state === AssistantState.CHAT_REPLY
                  ? 'Continue talking'
                  : 'Tap to speak with Serah'}
          </button>

          {(match ||
            state === AssistantState.CLARIFYING ||
            state === AssistantState.RESULTS ||
            state === AssistantState.EMERGENCY ||
            state === AssistantState.CHAT_REPLY) && (
            <button
              type="button"
              onClick={() => void onNewRequest()}
              disabled={clearing || busy || listening}
              className="mt-2 rounded-full border border-hair px-5 py-2 text-xs text-muted transition hover:border-amber hover:text-amber disabled:opacity-50"
            >
              {clearing ? 'Clearing…' : 'New request'}
            </button>
          )}
        </section>

        {import.meta.env.DEV && <StateStepper />}
    </div>
  );
}
