import { Link } from 'react-router-dom';
import { Activity, Mic, Send } from 'lucide-react';
import { AssistantState, goalRingProgress, nextMissingField } from '@care-plus/core';
import { useAuth } from '../auth/AuthContext';
import { useCaregiverProfile } from '../auth/useCaregiverProfile';
import { usePatientProfile } from '../auth/usePatientProfile';
import { useAssistant } from '../assistant/store';
import { ChatBubbles } from '../assistant/ChatBubbles';
import { EntityChips } from '../assistant/EntityChips';
import { Transcript } from '../assistant/Transcript';
import { StateStepper } from '../assistant/StateStepper';
import { MatchSearchPanel } from '../assistant/MatchSearchPanel';
import { LanguagePicker } from '../assistant/LanguagePicker';
import { NeuralOrb } from '../assistant/NeuralOrb';
import { useSerahEngine } from '../assistant/SerahEngine';
import { stateCopy } from '../assistant/locale';
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
  const {
    listening,
    busy,
    inputMode,
    setInputMode,
    textInput,
    setTextInput,
    mic,
    speech,
    turnError,
    consentNeeded,
    emergencyActive,
    visual,
    clearing,
    consentBtnRef,
    toggleMic,
    onGrantConsent,
    onNewRequest,
    onTextSubmit,
  } = useSerahEngine();
  const {
    state,
    intent,
    transcript,
    interim,
    match,
    matching,
    asleep,
    chat,
    uiLanguage,
    setUiLanguage,
  } = useAssistant();

  const progress = Math.round(goalRingProgress(intent) * 100);
  const missingField = nextMissingField(intent);
  const clarifyPrompt =
    state === AssistantState.CLARIFYING && missingField ? CLARIFY_PROMPTS[missingField] : null;
  const hologramText = interim || transcript || chat.at(-1)?.text || '';
  const showMatchPanel = matching || Boolean(match);

  return (
    <div className={`serah-immersive-container min-h-0 flex-1${showMatchPanel ? ' is-searching' : ''}`}>
      <div className={`serah-ambient-bg state-${visual}`} aria-hidden />

      <div className="serah-hud-top">
        <div className="hud-brand">
          <Activity color="var(--cp-accent-cyan)" size={20} />
          <span>SERAH NEURAL CORE v2.0</span>
        </div>
        <div className="hud-status">
          <div className="status-indicator" />
          <span>{asleep ? 'SLEEPING' : visual.toUpperCase()}</span>
          <span className="hud-goal">Goal {progress}%</span>
        </div>
        <LanguagePicker
          value={uiLanguage}
          onChange={setUiLanguage}
          disabled={listening || busy}
          className="justify-end"
        />
      </div>

      {!showMatchPanel &&
        ((user?.role === 'patient' && !canRequestCare) ||
          (user?.role === 'caregiver' && !isMatchEligible)) && (
        <div className="serah-profile-banners">
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
      )}

      {emergencyActive && (
        <div className="serah-emergency-banner">
          <p className="font-display text-sm tracking-wide text-rose">EMERGENCY alert</p>
          <p className="mt-1 text-xs text-muted">
            Serah detected a critical health signal and pushed your nearest advanced caregiver.
          </p>
          <a href="#emergency-match" className="mt-2 inline-block text-xs font-semibold text-rose">
            View emergency match
          </a>
        </div>
      )}

      <div className={`serah-stage${showMatchPanel ? ' is-searching' : ''}`}>
        <div className="serah-core-wrapper">
          <div className="serah-neural-field">
            <div aria-hidden>
              <NeuralOrb
                variant="stage"
                visual={visual}
                state={state}
                amplitude={Math.max(mic.amplitude, showMatchPanel ? 0.28 : 0.16)}
              />
            </div>
            <button
              type="button"
              onClick={() => void toggleMic()}
              aria-pressed={listening}
              aria-label={listening ? 'Stop listening' : 'Tap to speak'}
              className={`serah-orb-hit ${listening ? 'active' : ''}`}
            >
              <span className="serah-orb-hit-ring" />
            </button>
            {showMatchPanel ? (
              <div className="serah-field-chat">
                <ChatBubbles messages={chat} compact />
              </div>
            ) : null}
          </div>
          {!showMatchPanel ? (
            <>
              {asleep || state !== AssistantState.IDLE ? (
                <p className="serah-field-status" aria-live="polite">
                  {asleep ? 'Sleeping — say Hey Serah to wake me' : stateCopy(state, uiLanguage)}
                </p>
              ) : null}
              <div className="serah-core-chat">
                {hologramText ? (
                  <div className="hologram-transcript visible">
                    <p>{hologramText}</p>
                  </div>
                ) : (
                  <p className="serah-field-hint">Tap the field or type below to talk with Serah.</p>
                )}
                <ChatBubbles messages={chat} />
                {clarifyPrompt && (
                  <p className="mt-2 max-w-md text-center text-sm text-amber" aria-live="polite">
                    {clarifyPrompt} Keep talking — your other details stay.
                  </p>
                )}
                <div className="mt-3">
                  <EntityChips intent={intent} uiLanguage={uiLanguage} hideEmpty />
                </div>
                <Transcript transcript={transcript} interim={interim} />
              </div>
            </>
          ) : null}
        </div>

        {showMatchPanel ? (
          <div className="serah-match-projection is-open">
            <MatchSearchPanel
              id={emergencyActive ? 'emergency-match' : undefined}
              matching={matching}
              match={match}
              canRequestCare={canRequestCare}
              uiLanguage={uiLanguage}
            />
          </div>
        ) : null}
      </div>

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

        <div className="serah-hud-dock">
          {inputMode === 'voice' ? (
            <>
              <button
                type="button"
                onClick={() => void toggleMic()}
                disabled={busy && !listening}
                aria-pressed={listening}
                className={`serah-mic-btn ${listening ? 'active' : ''}`}
              >
                <Mic size={22} />
              </button>
              <span className="text-xs font-medium text-muted">
                {listening
                  ? 'Tap to stop'
                  : matching
                    ? 'Searching — keep chatting'
                    : busy
                      ? 'Serah is speaking…'
                      : asleep
                        ? 'Say Hey Serah'
                        : 'Tap to speak'}
              </span>
              <button
                type="button"
                className="text-xs font-semibold text-cyan hover:underline"
                onClick={() => setInputMode('text')}
              >
                Type instead
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
                className="min-h-10 flex-1 rounded-xl border border-hair bg-panel px-3.5 text-sm text-mist outline-none focus:border-cyan"
                autoFocus
                placeholder={asleep ? 'Say or type Hey Serah…' : 'Type your care need…'}
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                disabled={listening}
              />
              <Button
                type="submit"
                disabled={!textInput.trim() || listening}
                className="min-h-10 px-4"
              >
                <Send size={18} />
              </Button>
            </form>
          )}

          {(match ||
            matching ||
            state === AssistantState.CLARIFYING ||
            state === AssistantState.RESULTS ||
            state === AssistantState.EMERGENCY ||
            state === AssistantState.CHAT_REPLY) && (
            <button
              type="button"
              onClick={() => void onNewRequest()}
              disabled={clearing || busy || listening}
              className="rounded-xl border border-hair px-4 py-2 text-xs text-muted transition hover:border-amber hover:text-amber disabled:opacity-50"
            >
              {clearing ? 'Clearing…' : 'New request'}
            </button>
          )}
        </div>
      </div>

      {import.meta.env.DEV && !showMatchPanel && <StateStepper />}
    </div>
  );
}
