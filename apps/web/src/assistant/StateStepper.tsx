import { AssistantState, STATE_COPY } from '@care-plus/core';
import { useAssistant } from './store';

const STEP_ORDER: AssistantState[] = [
  AssistantState.IDLE,
  AssistantState.LISTENING,
  AssistantState.THINKING,
  AssistantState.CLARIFYING,
  AssistantState.SPEAKING,
  AssistantState.CHAT_REPLY,
  AssistantState.MATCHING,
  AssistantState.RESULTS,
  AssistantState.EMERGENCY,
];

/**
 * Dev-only control to manually step the FSM and seed intent fields, so the
 * Neural Core color + Goal Ring can be verified without the full voice flow.
 */
export function StateStepper() {
  const { state, setState, setIntentField, reset } = useAssistant();

  return (
    <div className="mt-6 rounded-2xl border border-hair bg-panel p-4 backdrop-blur-md">
      <p className="mb-2 text-xs uppercase tracking-wide text-muted">
        Dev · step assistant states
      </p>
      <div className="flex flex-wrap gap-1.5">
        {STEP_ORDER.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setState(s, { force: true })}
            className={`rounded-md border px-2 py-1 text-xs transition ${
              state === s ? 'border-cyan text-cyan' : 'border-hair text-muted hover:border-cyan/40'
            }`}
          >
            {s}
          </button>
        ))}
      </div>
      <p className="mt-2 text-xs text-muted">{STATE_COPY[state]}</p>

      <p className="mb-2 mt-4 text-xs uppercase tracking-wide text-muted">Seed Goal Ring</p>
      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => setIntentField('condition', 'Diabetes')}
          className="rounded-md border border-cyan/40 px-2 py-1 text-xs text-cyan"
        >
          + condition
        </button>
        <button
          type="button"
          onClick={() => setIntentField('language', 'Sinhala')}
          className="rounded-md border border-violet/40 px-2 py-1 text-xs text-violet"
        >
          + language
        </button>
        <button
          type="button"
          onClick={() => setIntentField('care_level', 'intermediate')}
          className="rounded-md border border-mint/40 px-2 py-1 text-xs text-mint"
        >
          + care level
        </button>
        <button
          type="button"
          onClick={reset}
          className="rounded-md border border-hair px-2 py-1 text-xs text-muted hover:border-rose hover:text-rose"
        >
          reset
        </button>
      </div>
    </div>
  );
}
