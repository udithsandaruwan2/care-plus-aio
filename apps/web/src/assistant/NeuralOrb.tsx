import { lazy, Suspense } from 'react';
import { AssistantState } from '@care-plus/core';
import { useReducedMotion } from './useReducedMotion';
import './SerahHud.css';

const NeuralCoreCanvas = lazy(() =>
  import('../neural-core/NeuralCoreCanvas').then((m) => ({ default: m.NeuralCoreCanvas })),
);

export type OrbVisualState = 'idle' | 'listening' | 'processing' | 'speaking' | 'matching';

export function orbVisualState(
  state: AssistantState,
  listening: boolean,
  matching = false,
): OrbVisualState {
  if (matching && !listening) return 'matching';
  if (listening || state === AssistantState.LISTENING) return 'listening';
  if (state === AssistantState.THINKING) return 'processing';
  if (state === AssistantState.MATCHING || matching) return 'matching';
  if (state === AssistantState.SPEAKING || state === AssistantState.CHAT_REPLY) return 'speaking';
  return 'idle';
}

export function NeuralOrb({
  visual,
  state = AssistantState.IDLE,
  amplitude = 0.18,
  variant = 'stage',
  parallax,
}: {
  visual: OrbVisualState;
  state?: AssistantState;
  amplitude?: number;
  variant?: 'hud' | 'hero' | 'stage' | 'well' | 'dock';
  parallax?: { x: number; y: number };
}) {
  const reducedMotion = useReducedMotion();
  const layout = variant === 'stage' ? 'stage' : variant === 'dock' ? 'dock' : 'well';
  const shell =
    variant === 'stage'
      ? `neural-stage state-${visual}`
      : variant === 'dock'
        ? `neural-dock state-${visual}`
        : `neural-well state-${visual}`;

  return (
    <div className={shell}>
      <Suspense fallback={<div className="neural-field-canvas" />}>
        <NeuralCoreCanvas
          amplitude={amplitude}
          state={state}
          reducedMotion={reducedMotion}
          layout={layout}
          parallax={parallax}
          className="neural-field-canvas"
        />
      </Suspense>
    </div>
  );
}
