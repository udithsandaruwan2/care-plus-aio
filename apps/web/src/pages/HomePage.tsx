import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { brand } from '@care-plus/ui-tokens';
import { AssistantState, STATE_COPY, goalRingProgress, nextMissingField } from '@care-plus/core';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { useAuth } from '../auth/AuthContext';
import { api } from '../auth/api';
import { useMicAmplitude } from '../neural-core/useMicAmplitude';
import { useAssistant } from '../assistant/store';
import { useReducedMotion } from '../assistant/useReducedMotion';
import { GoalRing } from '../assistant/GoalRing';
import { EntityChips } from '../assistant/EntityChips';
import { Transcript } from '../assistant/Transcript';
import { StateStepper } from '../assistant/StateStepper';
import { useSpeechRecognition, type RecognitionLang } from '../assistant/useSpeechRecognition';
import { useIntentExtraction } from '../assistant/useIntentExtraction';
import { MatchResultCards } from '../assistant/MatchResultCards';
import { useMatch, useMatchSocket } from '../assistant/useMatch';

const CLARIFY_PROMPTS: Record<string, string> = {
  condition: 'What condition or symptom should I focus on?',
  language: 'Which language do you prefer for care?',
  care_level: 'How much support do you need — basic, intermediate, or advanced?',
};

const NeuralCoreCanvas = lazy(() =>
  import('../neural-core/NeuralCoreCanvas').then((m) => ({ default: m.NeuralCoreCanvas })),
);

const LANGS: { id: RecognitionLang; label: string }[] = [
  { id: 'si-LK', label: 'සිංහල' },
  { id: 'ta-LK', label: 'தமிழ்' },
  { id: 'en-US', label: 'EN' },
];

export function HomePage() {
  const { user, logout } = useAuth();
  const [health, setHealth] = useState<string>('…');
  const [lang, setLang] = useState<RecognitionLang>('si-LK');
  const mic = useMicAmplitude();
  const reducedMotion = useReducedMotion();
  const { state, intent, transcript, interim, match, matchError, setState, setInterim, appendTranscript, reset } =
    useAssistant();
  const {
    extract,
    extracting,
    error: intentError,
    consentNeeded,
    grantConsent,
  } = useIntentExtraction();
  const { runMatch } = useMatch();
  useMatchSocket();

  const speech = useSpeechRecognition({
    lang,
    onInterim: (text) => setInterim(text),
    onFinal: (text) => appendTranscript(text),
    onEnd: () => {
      mic.stop();
      // Silence / stop → understand what was said, filling the ring & chips.
      void extract(useAssistant.getState().transcript, lang);
    },
  });

  useEffect(() => {
    api
      .health()
      .then((h) => setHealth(`${h.status} · db ${h.db} · redis ${h.redis}`))
      .catch(() => setHealth('unreachable'));
  }, []);

  // SPEAKING (intent complete) → auto-run VEHMF → RESULTS cards.
  const prevState = useRef(state);
  useEffect(() => {
    if (state === AssistantState.SPEAKING && prevState.current !== AssistantState.SPEAKING) {
      void runMatch();
    }
    prevState.current = state;
  }, [state, runMatch]);

  const listening = mic.active || speech.listening;

  async function toggleMic() {
    if (listening) {
      // Stopping the recognizer fires `onEnd`, which runs intent extraction.
      speech.stop();
      mic.stop();
      return;
    }

    const current = useAssistant.getState().state;
    // Keep chips/transcript when answering a CLARIFYING follow-up; only wipe
    // for a brand-new session.
    if (current !== AssistantState.CLARIFYING) {
      reset();
    } else {
      setInterim('');
    }
    await mic.start();
    speech.start();
    setState(AssistantState.LISTENING, { force: true });
  }

  async function onGrantConsent() {
    const ok = await grantConsent();
    if (ok) void extract(useAssistant.getState().transcript, lang);
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
          <button
            type="button"
            onClick={logout}
            className="shrink-0 rounded-lg border border-hair px-3 py-1.5 text-sm text-muted transition hover:border-rose hover:text-rose"
          >
            Sign out
          </button>
        </div>

        {/* Language selector */}
        <div className="mx-auto mt-6 flex gap-1.5">
          {LANGS.map((l) => (
            <button
              key={l.id}
              type="button"
              onClick={() => setLang(l.id)}
              disabled={listening}
              className={`rounded-full border px-3 py-1 text-sm transition disabled:opacity-50 ${
                lang === l.id
                  ? 'border-cyan text-cyan'
                  : 'border-hair text-muted hover:border-cyan/40'
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>

        {/* Neural Core inside the Goal Ring */}
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
            {state} · {extracting ? 'Understanding…' : STATE_COPY[state]}
          </p>
          {clarifyPrompt && (
            <p className="mt-1 text-sm text-amber" aria-live="polite">
              {clarifyPrompt} Tap below to answer — your other details stay.
            </p>
          )}
          {state === AssistantState.MATCHING && (
            <p className="mt-1 text-sm text-violet" aria-live="polite">
              Finding your best caregivers…
            </p>
          )}
          {state === AssistantState.SPEAKING && (
            <p className="mt-1 text-sm text-mint" aria-live="polite">
              Got it — matching caregivers now.
            </p>
          )}
          {(mic.error || speech.error) && (
            <p className="mt-1 text-sm text-rose">{mic.error ?? speech.error}</p>
          )}
          {(intentError || matchError) && !consentNeeded && (
            <p className="mt-1 text-sm text-rose">{intentError ?? matchError}</p>
          )}
          {consentNeeded && (
            <div className="mt-3 w-full max-w-sm rounded-xl border border-amber/40 bg-amber/5 p-4 text-center">
              <p className="text-sm text-amber">{intentError}</p>
              <button
                type="button"
                onClick={onGrantConsent}
                className="mt-3 rounded-full bg-amber/90 px-5 py-2 text-sm font-medium text-void transition hover:bg-amber"
              >
                Enable AI processing
              </button>
              <p className="mt-2 text-xs text-muted">
                You can revoke this anytime in your privacy settings.
              </p>
            </div>
          )}
          {!speech.supported && (
            <p className="mt-1 text-xs text-amber">
              Speech recognition unsupported here — try Chrome/Edge.
            </p>
          )}
          <p className="mt-1 text-xs text-muted">
            Goal {progress}% · level {(mic.amplitude * 100).toFixed(0)}%
          </p>

          <Transcript transcript={transcript} interim={interim} />
          <div className="mt-3">
            <EntityChips intent={intent} />
          </div>

          {match && (state === AssistantState.RESULTS || state === AssistantState.MATCHING) && (
            <MatchResultCards match={match} />
          )}

          <button
            type="button"
            onClick={toggleMic}
            disabled={extracting || state === AssistantState.MATCHING}
            className={`mt-4 rounded-full px-6 py-2.5 text-sm font-medium transition disabled:opacity-50 ${
              listening
                ? 'bg-rose/20 text-rose ring-1 ring-rose/50'
                : 'bg-cyan/90 text-void hover:bg-cyan'
            }`}
          >
            {listening
              ? 'Stop'
              : state === AssistantState.CLARIFYING
                ? 'Tap to answer'
                : state === AssistantState.RESULTS
                  ? 'New request'
                  : 'Tap to speak'}
          </button>
        </section>

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
            Speak a care need — the Neural Core fills the Goal Ring, then VEHMF
            ranks caregivers with score breakdown and an explanation.
          </p>
        </div>
      </main>
    </AtmosphereShell>
  );
}
