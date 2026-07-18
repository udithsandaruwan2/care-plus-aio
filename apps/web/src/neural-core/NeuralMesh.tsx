import { useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { colors } from '@care-plus/ui-tokens';
import type { AssistantState } from '@care-plus/core';
import { AssistantState as S } from '@care-plus/core';

const STATE_COLOR: Record<AssistantState, string> = {
  [S.IDLE]: colors.accentCyan,
  [S.LISTENING]: colors.accentCyan,
  [S.THINKING]: colors.accentViolet,
  [S.CLARIFYING]: colors.accentViolet,
  [S.SPEAKING]: colors.accentAmber,
  [S.MATCHING]: colors.accentViolet,
  [S.RESULTS]: colors.accentMint,
  [S.EMERGENCY]: colors.accentRose,
};

/** Volume-filling neuron count — dense enough to read as a brain, light enough for 60fps. */
const NEURON_COUNT = 420;
const RADIUS = 1.12;
/** Max synapse length (world units). */
const LINK_DISTANCE = 0.38;
/** Cap synapse segments so the mesh stays cheap. */
const MAX_LINKS = 640;

type NeuralMeshProps = {
  amplitude: number;
  state: AssistantState;
  /** When false, skip continuous animation (idle static frame). */
  animate: boolean;
};

/** Deterministic PRNG so the neuron cloud is stable across renders. */
function mulberry32(seed: number) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Organic Neural Core: a volume-filled point cloud of neurons + synapse chords.
 * No solid fill mesh — glow comes from additive points/lines only, so amplitude
 * never "paints a square" inside the canvas.
 */
export function NeuralMesh({ amplitude, state, animate }: NeuralMeshProps) {
  const group = useRef<THREE.Group>(null);
  const pointsMat = useRef<THREE.PointsMaterial>(null);
  const lineMat = useRef<THREE.LineBasicMaterial>(null);
  const hazeMat = useRef<THREE.MeshBasicMaterial>(null);
  const { invalidate } = useThree();
  const color = useMemo(() => new THREE.Color(STATE_COLOR[state]), [state]);

  const { positions, linePositions } = useMemo(() => {
    const rand = mulberry32(20260718);
    const neurons: THREE.Vector3[] = [];

    for (let i = 0; i < NEURON_COUNT; i++) {
      // Uniform sphere directions; radius bias leaves a denser cortex shell
      // with enough interior volume that the core reads as a living brain.
      const u = rand();
      const v = rand();
      const theta = Math.acos(2 * u - 1);
      const phi = 2 * Math.PI * v;
      const shell = rand();
      // ~55% near the cortex shell, rest fill the interior.
      const r =
        shell < 0.55 ? RADIUS * (0.72 + 0.28 * rand()) : RADIUS * (0.12 + 0.6 * Math.cbrt(rand()));
      neurons.push(
        new THREE.Vector3(
          r * Math.sin(theta) * Math.cos(phi),
          r * Math.sin(theta) * Math.sin(phi),
          r * Math.cos(theta),
        ),
      );
    }

    const positions = new Float32Array(neurons.length * 3);
    neurons.forEach((p, i) => {
      positions[i * 3] = p.x;
      positions[i * 3 + 1] = p.y;
      positions[i * 3 + 2] = p.z;
    });

    const segs: number[] = [];
    const linkDistSq = LINK_DISTANCE * LINK_DISTANCE;
    for (let i = 0; i < neurons.length && segs.length < MAX_LINKS * 6; i++) {
      // Prefer a few nearest neighbours over an all-pairs flood.
      let linked = 0;
      for (let j = i + 1; j < neurons.length && linked < 4; j++) {
        if (neurons[i].distanceToSquared(neurons[j]) < linkDistSq) {
          segs.push(
            neurons[i].x,
            neurons[i].y,
            neurons[i].z,
            neurons[j].x,
            neurons[j].y,
            neurons[j].z,
          );
          linked += 1;
          if (segs.length >= MAX_LINKS * 6) break;
        }
      }
    }

    return { positions, linePositions: new Float32Array(segs) };
  }, []);

  useFrame(({ clock }) => {
    if (!animate) return;
    const t = clock.getElapsedTime();
    // Clamp audio drive so loud mic input can't turn the cloud into a solid blob.
    const amp = Math.min(amplitude, 0.55);
    const breath = 1 + Math.sin(t * 1.35) * 0.028;
    const pulse = 1 + amp * 0.18;
    if (group.current) {
      group.current.scale.setScalar(breath * pulse);
      group.current.rotation.y = t * (0.1 + amp * 0.45);
      group.current.rotation.x = Math.sin(t * 0.38) * 0.1;
      group.current.rotation.z = Math.cos(t * 0.22) * 0.04;
    }
    if (pointsMat.current) {
      pointsMat.current.color.copy(color);
      pointsMat.current.opacity = 0.55 + amp * 0.35;
      pointsMat.current.size = 0.028 + amp * 0.018;
    }
    if (lineMat.current) {
      lineMat.current.color.copy(color);
      lineMat.current.opacity = 0.18 + amp * 0.32;
    }
    if (hazeMat.current) {
      hazeMat.current.color.copy(color);
      hazeMat.current.opacity = 0.03 + amp * 0.06;
    }
    invalidate();
  });

  return (
    <group ref={group}>
      {/* Soft volumetric haze — additive + tiny opacity so it never reads as a fill. */}
      <mesh>
        <sphereGeometry args={[0.78, 32, 32]} />
        <meshBasicMaterial
          ref={hazeMat}
          color={color}
          transparent
          opacity={0.03}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* Neuron somas. */}
      <points>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        </bufferGeometry>
        <pointsMaterial
          ref={pointsMat}
          color={color}
          size={0.03}
          sizeAttenuation
          transparent
          opacity={0.65}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>

      {/* Synaptic links between neighbouring neurons. */}
      <lineSegments>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[linePositions, 3]} />
        </bufferGeometry>
        <lineBasicMaterial
          ref={lineMat}
          color={color}
          transparent
          opacity={0.22}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </lineSegments>
    </group>
  );
}
