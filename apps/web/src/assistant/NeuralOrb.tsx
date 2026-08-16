import { lazy, Suspense } from 'react';
import { AssistantState } from '@care-plus/core';
import { useReducedMotion } from './useReducedMotion';
import './SerahHud.css';

const NeuralCoreCanvas = lazy(() =>
  import('../neural-core/NeuralCoreCanvas').then((m) => ({ default: m.NeuralCoreCanvas })),
);

export type OrbVisualState = 'idle' | 'listening' | 'processing' | 'speaking' | 'matching';

export function orbVisualState(state: AssistantState, listening: boolean): OrbVisualState {
  if (listening || state === AssistantState.LISTENING) return 'listening';
  if (state === AssistantState.THINKING) return 'processing';
  if (state === AssistantState.MATCHING) return 'matching';
  if (state === AssistantState.SPEAKING || state === AssistantState.CHAT_REPLY) return 'speaking';
  return 'idle';
}

export function NeuralOrb({
  visual,
  state = AssistantState.IDLE,
  amplitude = 0.18,
  variant = 'hud',
}: {
  visual: OrbVisualState;
  state?: AssistantState;
  amplitude?: number;
  variant?: 'hud' | 'hero';
}) {
  const reducedMotion = useReducedMotion();

  return (
    <div className={`neural-orb state-${visual} ${variant === 'hero' ? 'neural-orb-hero' : ''}`}>
      <div className="orb-ring orb-ring-1" />
      <div className="orb-ring orb-ring-2" />
      <div className="orb-ring orb-ring-3" />
      <div className="orb-core">
        <Suspense fallback={<div className="orb-core-canvas" />}>
          <NeuralCoreCanvas
            amplitude={amplitude}
            state={state}
            reducedMotion={reducedMotion}
            className="orb-core-canvas"
          />
        </Suspense>
      </div>
    </div>
  );
}
