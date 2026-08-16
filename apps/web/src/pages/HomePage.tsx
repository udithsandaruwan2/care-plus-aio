import { FormEvent, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, Mic, Send } from 'lucide-react';
import { AssistantState, goalRingProgress, nextMissingField } from '@care-plus/core';
import { useAuth } from '../auth/AuthContext';
import { useCaregiverProfile } from '../auth/useCaregiverProfile';
import { usePatientProfile } from '../auth/usePatientProfile';
import { api } from '../auth/api';
import { useMicAmplitude } from '../neural-core/useMicAmplitude';
import { useAssistant } from '../assistant/store';
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
import { NeuralOrb, orbVisualState } from '../assistant/NeuralOrb';
import { stateCopy } from '../assistant/locale';
import { uiLanguageToRecognition } from '../assistant/uiVoiceLanguage';
import { Button } from '../components/ui/Button';
import '../assistant/SerahHud.css';

const CLARIFY_PROMPTS: Record<string, string> = {
  condition: 'What condition or symptom should I focus on?',
  language: 'Which language do you prefer for care?',
  care_level: 'How much support do you need — basic, intermediate, or advanced?',
};

export function HomePage() {
  const { user } = useAuth();
  const { canRequestCare, completionPercent } = usePatientProfile();
  const { isMatchEligible, completionPercent: cgCompletion } = useCaregiverProfile();
  const [emergencyMatchId, setEmergencyMatchId] = useState<number | null>(null);
  const [conversationOn, setConversationOn] = useState(false);
  const [inputMode, setInputMode] = useState<'voice' | 'text'>('voice');
  const [textInput, setTextInput] = useState('');
  const conversationOnRef = useRef(false);
  conversationOnRef.current = conversationOn;
  const mic = useMicAmplitude();
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
  const visual = orbVisualState(state, listening);
  const showMatches = Boolean(match?.results?.length);

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

  async function onTextSubmit(e: FormEvent) {
    e.preventDefault();
    const line = textInput.trim();
    if (!line || busy || listening) return;
    setTextInput('');
    await runTurn({ text: line, audio: null });
  }

  const progress = Math.round(goalRingProgress(intent) * 100);
  const missingField = nextMissingField(intent);
  const clarifyPrompt =
    state === AssistantState.CLARIFYING && missingField ? CLARIFY_PROMPTS[missingField] : null;
  const hologramText = interim || transcript || chat.at(-1)?.text || '';

  return (
    <div className="serah-immersive-container">
      <div className={`serah-ambient-bg state-${visual}`} aria-hidden />

      <div className="serah-hud-top">
        <div className="hud-brand">
          <Activity color="var(--cp-accent-cyan)" size={22} />
          <span>SERAH NEURAL CORE v2.0</span>
        </div>
        <div className="hud-status">
          <div className="status-indicator" />
          <span>{visual.toUpperCase()}</span>
        </div>
        <LanguagePicker
          value={uiLanguage}
          onChange={setUiLanguage}
          disabled={listening || busy}
          className="justify-end"
        />
      </div>

      <div className="relative z-10 mx-auto flex w-full max-w-5xl flex-wrap justify-center gap-2 px-4 pt-3 text-xs">
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

      {emergencyActive && (
        <div className="relative z-10 mx-auto mt-3 w-full max-w-lg rounded-2xl border border-rose/50 bg-rose/10 p-4 text-left">
          <p className="font-display text-sm tracking-wide text-rose">EMERGENCY alert</p>
          <p className="mt-1 text-xs text-muted">
            Serah detected a critical health signal and pushed your nearest advanced caregiver.
          </p>
          <a href="#emergency-match" className="mt-3 inline-block text-xs font-semibold text-rose">
            View emergency match
          </a>
        </div>
      )}

      <div className={`serah-core-wrapper ${showMatches ? 'shifted' : ''}`}>
        <button
          type="button"
          onClick={() => void toggleMic()}
          aria-pressed={listening}
          aria-label={listening ? 'Stop listening' : 'Tap to speak'}
          className="cursor-pointer rounded-full border-0 bg-transparent p-0 outline-none focus-visible:ring-2 focus-visible:ring-cyan"
        >
          <NeuralOrb visual={visual} />
        </button>
        <p className="mt-3 font-display text-sm tracking-wide text-cyan" aria-live="polite">
          {stateCopy(state, uiLanguage)} · Goal {progress}%
        </p>
        <div className={`hologram-transcript ${hologramText ? 'visible' : ''}`}>
          <p>{hologramText || 'Tap the orb or type below to talk with Serah.'}</p>
        </div>
        <ChatBubbles messages={chat} />
        {clarifyPrompt && (
          <p className="mt-2 max-w-md text-center text-sm text-amber" aria-live="polite">
            {clarifyPrompt} Keep talking — your other details stay.
          </p>
        )}
        <div className="mt-3">
          <EntityChips intent={intent} uiLanguage={uiLanguage} />
        </div>
        <Transcript transcript={transcript} interim={interim} />
      </div>

      {showMatches ? (
        <div className="serah-match-projection mx-auto lg:absolute lg:right-8 lg:top-28 lg:mx-0">
          <MatchResultCards
            id={emergencyActive ? 'emergency-match' : undefined}
            match={match!}
            canRequestCare={canRequestCare}
            uiLanguage={uiLanguage}
          />
        </div>
      ) : null}

      <div className="serah-hud-bottom">
        {(mic.error || speech.error) && (
          <p className="text-sm text-rose" role="alert">
            {mic.error ?? speech.error}
          </p>
        )}
        {turnError && !consentNeeded && (
          <p className="text-sm text-rose" role="alert">
            {turnError}
          </p>
        )}
        {consentNeeded && (
          <div
            className="w-full max-w-sm rounded-xl border border-amber/40 bg-amber/5 p-4 text-center"
            role="alertdialog"
            aria-labelledby="consent-title"
          >
            <p id="consent-title" className="text-sm text-amber">
              {turnError}
            </p>
            <button
              ref={consentBtnRef}
              type="button"
              onClick={() => void onGrantConsent()}
              className="mt-3 rounded-xl bg-amber px-5 py-2 text-sm font-semibold text-inverse"
            >
              Enable AI processing
            </button>
          </div>
        )}
        {!speech.supported && (
          <p className="text-xs text-amber" role="status">
            Live captions unsupported here — audio still uploads for Serah (try Chrome/Edge).
          </p>
        )}

        {inputMode === 'voice' ? (
          <>
            <button
              type="button"
              onClick={() => void toggleMic()}
              disabled={busy && !listening}
              aria-pressed={listening}
              className={`serah-mic-btn ${listening ? 'active' : ''}`}
            >
              <Mic size={28} />
            </button>
            <span className="text-xs font-medium text-muted">
              {listening ? 'Tap to stop' : busy ? 'Serah is speaking…' : 'Tap to speak'}
            </span>
            <button
              type="button"
              className="text-xs font-semibold text-cyan hover:underline"
              onClick={() => setInputMode('text')}
            >
              Or type a message…
            </button>
          </>
        ) : (
          <form className="serah-text-controls" onSubmit={(e) => void onTextSubmit(e)}>
            <button
              type="button"
              className="rounded-xl border border-hair px-3 text-cyan"
              onClick={() => setInputMode('voice')}
              aria-label="Switch to voice"
            >
              <Mic size={18} />
            </button>
            <input
              className="min-h-11 flex-1 rounded-xl border border-hair bg-panel px-3.5 text-sm text-mist outline-none focus:border-cyan"
              autoFocus
              placeholder="Type your care need…"
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              disabled={busy || listening}
            />
            <Button type="submit" disabled={!textInput.trim() || busy} className="min-h-11 px-4">
              <Send size={18} />
            </Button>
          </form>
        )}

        {(match ||
          state === AssistantState.CLARIFYING ||
          state === AssistantState.RESULTS ||
          state === AssistantState.EMERGENCY ||
          state === AssistantState.CHAT_REPLY) && (
          <button
            type="button"
            onClick={() => void onNewRequest()}
            disabled={clearing || busy || listening}
            className="rounded-xl border border-hair px-5 py-2 text-xs text-muted transition hover:border-amber hover:text-amber disabled:opacity-50"
          >
            {clearing ? 'Clearing…' : 'New request'}
          </button>
        )}
      </div>

      {import.meta.env.DEV && <StateStepper />}
    </div>
  );
}
