import { Suspense, useEffect } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { Bloom, EffectComposer } from '@react-three/postprocessing';
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
 * `frameloop="demand"` — idle stays on a single static frame (~0% GPU);
 * while listening/animating, the mesh calls `invalidate()` each frame.
 */
export function NeuralCoreCanvas({ amplitude, state, className, reducedMotion }: Props) {
  const animate =
    !reducedMotion &&
    (state === S.LISTENING ||
      state === S.THINKING ||
      state === S.MATCHING ||
      state === S.EMERGENCY ||
      amplitude > 0.02);

  return (
    <div className={className} style={{ width: '100%', height: '100%' }}>
      <Canvas
        frameloop="demand"
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 3.4], fov: 42 }}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
        style={{ background: 'transparent' }}
      >
        <DemandController animate={animate} />
        <ambientLight intensity={0.35} />
        <pointLight position={[3, 2, 4]} intensity={1.2} color="#22D3EE" />
        <pointLight position={[-3, -1, 2]} intensity={0.6} color="#8B5CF6" />
        <Suspense fallback={null}>
          <NeuralMesh amplitude={amplitude} state={state} animate={animate} />
          <EffectComposer multisampling={0}>
            <Bloom
              intensity={0.55 + amplitude * 0.9}
              luminanceThreshold={0.15}
              luminanceSmoothing={0.4}
              mipmapBlur
            />
          </EffectComposer>
        </Suspense>
      </Canvas>
    </div>
  );
}
