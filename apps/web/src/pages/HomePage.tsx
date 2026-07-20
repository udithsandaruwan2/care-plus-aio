import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { brand } from '@care-plus/ui-tokens';
import { AssistantState, goalRingProgress, nextMissingField } from '@care-plus/core';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { useAuth } from '../auth/AuthContext';
import { useCurrentCareRelationship } from '../auth/useCurrentCareRelationship';
import { ActiveCareLinkCard } from '../components/ActiveCareLinkCard';
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
import {
  uiLanguageLabel,
  uiLanguageToRecognition,
} from '../assistant/uiVoiceLanguage';

const CLARIFY_PROMPTS: Record<string, string> = {
  condition: 'What condition or symptom should I focus on?',
  language: 'Which language do you prefer for care?',
  care_level: 'How much support do you need — basic, intermediate, or advanced?',
};

const NeuralCoreCanvas = lazy(() =>
  import('../neural-core/NeuralCoreCanvas').then((m) => ({ default: m.NeuralCoreCanvas })),
);

export function HomePage() {
  const { user, logout } = useAuth();
  const { canRequestCare, completionPercent } = usePatientProfile();
  const { isMatchEligible, completionPercent: cgCompletion } = useCaregiverProfile();
  const [health, setHealth] = useState<string>('…');
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
    asrSource,
    asrHeardLang,
    ttsSource,
    stopSpeaking,
  } = useVoiceTurn();
  const care = useCurrentCareRelationship();
  useMatchSocket({ onCareRelationshipUpdated: () => void care.refresh() });

  const endingRef = useRef(false);
  const resumeListeningRef = useRef<() => Promise<void>>(async () => {});
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

  useEffect(() => {
    api
      .health()
      .then((h) => setHealth(`${h.status} · db ${h.db} · redis ${h.redis}`))
      .catch(() => setHealth('unreachable'));
  }, []);

  const listening = mic.active || speech.listening;

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
    <AtmosphereShell>
      <main className="mx-auto flex min-h-full max-w-3xl flex-col px-6 py-10">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-display text-sm uppercase tracking-[0.2em] text-cyan">
              {brand.theme}
            </p>
            <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight text-mist sm:text-5xl">
              {brand.name}
            </h1>
          </div>
          <div className="flex shrink-0 gap-2">
            <Link
              to="/catalog"
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted transition hover:border-cyan hover:text-cyan"
            >
              Packages
            </Link>
            <Link
              to="/contact"
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted transition hover:border-cyan hover:text-cyan"
            >
              Contact
            </Link>
            <Link
              to="/caregivers"
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted transition hover:border-cyan hover:text-cyan"
            >
              Browse
            </Link>
            {user?.role === 'admin' && (
              <Link
                to="/leads"
                className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted transition hover:border-amber hover:text-amber"
              >
                Leads
              </Link>
            )}
            {user?.role === 'patient' && !canRequestCare && (
              <Link
                to="/onboarding"
                className="rounded-lg border border-amber/40 px-3 py-1.5 text-sm text-amber transition hover:border-amber hover:bg-amber/10"
              >
                Profile {completionPercent}%
              </Link>
            )}
            {user?.role === 'patient' && (
              <Link
                to="/requests"
                className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted transition hover:border-cyan hover:text-cyan"
              >
                Requests
              </Link>
            )}
            {user?.role === 'caregiver' && !isMatchEligible && (
              <Link
                to="/caregiver-onboarding"
                className="rounded-lg border border-amber/40 px-3 py-1.5 text-sm text-amber transition hover:border-amber hover:bg-amber/10"
              >
                Profile {cgCompletion}%
              </Link>
            )}
            {user?.role === 'caregiver' && (
              <Link
                to="/requests"
                className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted transition hover:border-cyan hover:text-cyan"
              >
                Inbox
              </Link>
            )}
            {user?.role === 'caregiver' && (
              <Link
                to="/presence"
                className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted transition hover:border-mint hover:text-mint"
              >
                Presence
              </Link>
            )}
            <button
              type="button"
              onClick={logout}
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted transition hover:border-rose hover:text-rose"
            >
              Sign out
            </button>
          </div>
        </div>

        <LanguagePicker
          value={uiLanguage}
          onChange={setUiLanguage}
          disabled={listening || busy}
        />

        <p className="mx-auto mt-3 max-w-md text-center text-xs text-muted">
          lang <span className="text-cyan">{uiLanguageLabel(uiLanguage)}</span>
          {asrSource ? ` · ASR ${asrSource}` : ''}
          {ttsSource ? ` · TTS ${ttsSource}` : ''}
          {asrHeardLang ? ` · heard ${asrHeardLang}` : ''}
          <br />
          Pick a language, then speak. Audio uses local Whisper; Serah replies in the same language.
          Pause after speaking — she answers automatically.
        </p>

        <section className="relative mx-auto mt-4 flex w-full max-w-lg flex-col items-center">
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
                    Loading Neural Core…
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
            <p className="mt-1 text-sm text-rose">{mic.error ?? speech.error}</p>
          )}
          {turnError && !consentNeeded && <p className="mt-1 text-sm text-rose">{turnError}</p>}
          {consentNeeded && (
            <div className="mt-3 w-full max-w-sm rounded-xl border border-amber/40 bg-amber/5 p-4 text-center">
              <p className="text-sm text-amber">{turnError}</p>
              <button
                type="button"
                onClick={onGrantConsent}
                className="mt-3 rounded-full bg-amber/90 px-5 py-2 text-sm font-medium text-void transition hover:bg-amber"
              >
                Enable AI processing
              </button>
            </div>
          )}
          {!speech.supported && (
            <p className="mt-1 text-xs text-amber">
              Live captions unsupported here — audio still uploads for Serah (try Chrome/Edge).
            </p>
          )}
          <p className="mt-1 text-xs text-muted">
            Goal {progress}% · level {(mic.amplitude * 100).toFixed(0)}%
          </p>

          <Transcript transcript={transcript} interim={interim} />
          <div className="mt-3">
            <EntityChips intent={intent} uiLanguage={uiLanguage} />
          </div>

          {match && (state === AssistantState.RESULTS || state === AssistantState.MATCHING) && (
            <MatchResultCards match={match} canRequestCare={canRequestCare} uiLanguage={uiLanguage} />
          )}

          <button
            type="button"
            onClick={toggleMic}
            disabled={busy && !listening}
            className={`mt-4 rounded-full px-6 py-2.5 text-sm font-medium transition disabled:opacity-50 ${
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
                    state === AssistantState.CHAT_REPLY
                  ? 'Continue talking'
                  : 'Tap to speak with Serah'}
          </button>

          {(match ||
            state === AssistantState.CLARIFYING ||
            state === AssistantState.RESULTS ||
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

        {care.relationship && (user?.role === 'patient' || user?.role === 'caregiver') && (
          <ActiveCareLinkCard
            relationship={care.relationship}
            role={user.role}
            onEnded={() => void care.refresh()}
          />
        )}

        {import.meta.env.DEV && <StateStepper />}

        <div className="mt-8 rounded-2xl border border-hair bg-panel p-5 backdrop-blur-md">
          <div className="flex items-center justify-between gap-4">
            <span className="text-sm text-muted">Signed in as</span>
            <span className="font-mono text-sm text-mint">
              {user?.email} · {user?.role}
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between gap-4">
            <span className="text-sm text-muted">API health</span>
            <span className="font-mono text-sm text-mint">{health}</span>
          </div>
          <p className="mt-4 text-sm text-muted">
            Choose Sinhala, Tamil, or English, then talk with Serah. She replies in that language,
            and when you need a caregiver VEHMF ranks matches with explanations.
          </p>
        </div>
      </main>
    </AtmosphereShell>
  );
}
