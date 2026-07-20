import { Suspense, useEffect } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import type { AssistantState } from '@care-plus/core';
import { AssistantState as S } from '@care-plus/core';
import { NeuralMesh } from './NeuralMesh';

type Props = {
  amplitude: number;
  state: AssistantState;
  className?: string;
  /** Force a static frame (accessibility). */
  reducedMotion?: boolean;
};

function DemandController({ animate }: { animate: boolean }) {
  const { invalidate } = useThree();
  useEffect(() => {
    // Paint one frame when props/state change; continuous loop only while animate.
    invalidate();
  }, [animate, invalidate]);
  return null;
}

/**
 * Audio-reactive Neural Core.
 *
 * Glow is built from additive neuron/synapse materials — not a full-frame Bloom
 * pass. Bloom previously painted a visible square matching the canvas bounds
 * when the core lit up.
 *
 * `frameloop="demand"` — idle stays on a single static frame (~0% GPU);
 * while listening/animating, the mesh calls `invalidate()` each frame.
 */
export function NeuralCoreCanvas({ amplitude, state, className, reducedMotion }: Props) {
  const animate =
    !reducedMotion &&
    (state === S.LISTENING ||
      state === S.THINKING ||
      state === S.CHAT_REPLY ||
      state === S.MATCHING ||
      state === S.EMERGENCY ||
      amplitude > 0.02);

  return (
    <div
      className={className}
      style={{
        width: '100%',
        height: '100%',
        borderRadius: '50%',
        overflow: 'hidden',
        background: 'transparent',
      }}
    >
      <Canvas
        frameloop="demand"
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 3.55], fov: 40 }}
        gl={{
          antialias: true,
          alpha: true,
          premultipliedAlpha: false,
          powerPreference: 'high-performance',
        }}
        onCreated={({ gl }) => {
          gl.setClearColor(0x000000, 0);
        }}
        style={{ background: 'transparent', width: '100%', height: '100%' }}
      >
        <DemandController animate={animate} />
        <Suspense fallback={null}>
          <NeuralMesh amplitude={amplitude} state={state} animate={animate} />
        </Suspense>
      </Canvas>
    </div>
  );
}
