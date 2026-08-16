import { AssistantState } from '@care-plus/core';

export type OrbVisualState = 'idle' | 'listening' | 'processing' | 'speaking' | 'matching';

export function orbVisualState(state: AssistantState, listening: boolean): OrbVisualState {
  if (listening || state === AssistantState.LISTENING) return 'listening';
  if (state === AssistantState.THINKING) return 'processing';
  if (state === AssistantState.MATCHING) return 'matching';
  if (state === AssistantState.SPEAKING || state === AssistantState.CHAT_REPLY) return 'speaking';
  return 'idle';
}

export function NeuralOrb({ visual }: { visual: OrbVisualState }) {
  return (
    <div className={`neural-orb state-${visual}`} aria-hidden>
      <div className="orb-ring ring-1" />
      <div className="orb-ring ring-2" />
      <div className="orb-ring ring-3" />
      <div className="orb-core" />
    </div>
  );
}
