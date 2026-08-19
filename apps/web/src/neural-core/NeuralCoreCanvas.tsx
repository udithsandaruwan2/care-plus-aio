import { Suspense, useEffect, useRef, useState, type MutableRefObject } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import type { AssistantState } from '@care-plus/core';
import { NeuralMesh } from './NeuralMesh';

export type NeuralLayout = 'stage' | 'well' | 'dock';

type Props = {
  amplitude: number;
  amplitudeRef?: MutableRefObject<number>;
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
  animate,
}: {
  parallax?: { x: number; y: number };
  z: number;
  animate: boolean;
}) {
  const { camera } = useThree();
  useFrame(() => {
    if (!animate) return;
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

function useInViewport(ref: MutableRefObject<HTMLElement | null>) {
  const [inView, setInView] = useState(true);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === 'undefined') return undefined;
    const io = new IntersectionObserver(
      (entries) => {
        const hit = entries[0];
        setInView(Boolean(hit?.isIntersecting && (hit.intersectionRatio ?? 0) > 0));
      },
      { threshold: 0.01 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [ref]);

  return inView;
}

/**
 * Audio-reactive Neural Core.
 *
 * Glow is built from additive neuron/synapse materials — not a full-frame Bloom
 * pass. Bloom previously painted a visible square matching the canvas bounds
 * when the core lit up.
 *
 * `frameloop="always"` while the canvas is on-screen and motion is allowed;
 * switches to `demand` (zero frames) when the tab is hidden, the canvas is
 * scrolled out of view, or reduced-motion is on. The mesh does not call
 * `invalidate()` in the always loop.
 */
export function NeuralCoreCanvas({
  amplitude,
  amplitudeRef,
  state,
  className,
  reducedMotion,
  layout = 'well',
  parallax,
}: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const pageVisible = usePageVisible();
  const inView = useInViewport(hostRef);
  const animate = !reducedMotion && pageVisible && inView;
  const stage = layout === 'stage';
  const dock = layout === 'dock';
  const cameraZ = dock ? 5.8 : stage ? 4.2 : 3.7;
  const spread = dock ? 0.82 : stage ? 1.18 : 1;
  const fov = dock ? 34 : stage ? 42 : 40;

  return (
    <div
      ref={hostRef}
      className={className}
      style={{
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        background: 'transparent',
      }}
    >
      <Canvas
        frameloop={animate ? 'always' : 'demand'}
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, cameraZ], fov }}
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
        <CameraRig parallax={parallax} z={cameraZ} animate={animate} />
        <Suspense fallback={null}>
          <NeuralMesh
            amplitude={amplitude}
            amplitudeRef={amplitudeRef}
            state={state}
            animate={animate}
            spread={spread}
            surface="light"
          />
        </Suspense>
      </Canvas>
    </div>
  );
}
