import { Suspense, useEffect, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import type { AssistantState } from '@care-plus/core';
import { NeuralMesh } from './NeuralMesh';

export type NeuralLayout = 'stage' | 'well';

type Props = {
  amplitude: number;
  state: AssistantState;
  className?: string;
  /** Force a static frame (accessibility). */
  reducedMotion?: boolean;
  /** Stage fills the Serah pane; well is the public hero. */
  layout?: NeuralLayout;
  /** Pointer NDC-ish offset (-1..1) for a light camera parallax. */
  parallax?: { x: number; y: number };
};

function DemandController({ animate }: { animate: boolean }) {
  const { invalidate } = useThree();
  useEffect(() => {
    invalidate();
  }, [animate, invalidate]);
  return null;
}

function CameraRig({
  parallax,
  z,
}: {
  parallax?: { x: number; y: number };
  z: number;
}) {
  const { camera } = useThree();
  useFrame(() => {
    const tx = (parallax?.x ?? 0) * 0.32;
    const ty = -(parallax?.y ?? 0) * 0.2;
    camera.position.x += (tx - camera.position.x) * 0.06;
    camera.position.y += (ty - camera.position.y) * 0.06;
    camera.position.z = z;
    camera.lookAt(0, 0, 0);
  });
  return null;
}

function usePageVisible() {
  const [visible, setVisible] = useState(
    () => typeof document === 'undefined' || document.visibilityState !== 'hidden',
  );

  useEffect(() => {
    const onVis = () => setVisible(document.visibilityState !== 'hidden');
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, []);

  return visible;
}

/**
 * Audio-reactive Neural Core.
 *
 * Glow is built from additive neuron/synapse materials — not a full-frame Bloom
 * pass. Bloom previously painted a visible square matching the canvas bounds
 * when the core lit up.
 *
 * `frameloop="demand"` — the mesh calls `invalidate()` each frame while motion
 * is allowed. Animation pauses when the tab is hidden.
 */
export function NeuralCoreCanvas({
  amplitude,
  state,
  className,
  reducedMotion,
  layout = 'well',
  parallax,
}: Props) {
  const pageVisible = usePageVisible();
  const animate = !reducedMotion && pageVisible;
  const stage = layout === 'stage';
  const cameraZ = stage ? 4.2 : 3.7;
  const spread = stage ? 1.18 : 1;

  return (
    <div
      className={className}
      style={{
        width: '100%',
        height: '100%',
        overflow: stage ? 'hidden' : 'visible',
        background: 'transparent',
      }}
    >
      <Canvas
        frameloop="demand"
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, cameraZ], fov: stage ? 42 : 40 }}
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
        <CameraRig parallax={parallax} z={cameraZ} />
        <Suspense fallback={null}>
          <NeuralMesh
            amplitude={amplitude}
            state={state}
            animate={animate}
            spread={spread}
            surface={stage ? 'dark' : 'light'}
          />
        </Suspense>
      </Canvas>
    </div>
  );
}
