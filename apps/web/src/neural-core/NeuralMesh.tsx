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

type NeuralMeshProps = {
  amplitude: number;
  state: AssistantState;
  /** When false, skip continuous animation (idle static frame). */
  animate: boolean;
};

export function NeuralMesh({ amplitude, state, animate }: NeuralMeshProps) {
  const group = useRef<THREE.Group>(null);
  const mat = useRef<THREE.MeshStandardMaterial>(null);
  const lineMat = useRef<THREE.LineBasicMaterial>(null);
  const { invalidate } = useThree();
  const color = useMemo(() => new THREE.Color(STATE_COLOR[state]), [state]);

  const { positions, linePositions } = useMemo(() => {
    const geo = new THREE.IcosahedronGeometry(1.1, 1);
    const pos = geo.attributes.position;
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i < pos.count; i++) {
      pts.push(new THREE.Vector3().fromBufferAttribute(pos, i));
    }
    // Unique vertices (icosahedron shares duplicates).
    const unique: THREE.Vector3[] = [];
    for (const p of pts) {
      if (!unique.some((u) => u.distanceToSquared(p) < 1e-6)) unique.push(p.clone());
    }
    const positions = new Float32Array(unique.length * 3);
    unique.forEach((p, i) => {
      positions[i * 3] = p.x;
      positions[i * 3 + 1] = p.y;
      positions[i * 3 + 2] = p.z;
    });

    // Synapse chords between nearby vertices (keep count low for perf).
    const segs: number[] = [];
    for (let i = 0; i < unique.length; i++) {
      for (let j = i + 1; j < unique.length; j++) {
        if (unique[i].distanceTo(unique[j]) < 1.35) {
          segs.push(
            unique[i].x,
            unique[i].y,
            unique[i].z,
            unique[j].x,
            unique[j].y,
            unique[j].z,
          );
        }
      }
    }
    geo.dispose();
    return { positions, linePositions: new Float32Array(segs) };
  }, []);

  useFrame(({ clock }) => {
    if (!animate) return;
    const t = clock.getElapsedTime();
    const breath = 1 + Math.sin(t * 1.4) * 0.03;
    const pulse = 1 + amplitude * 0.35;
    if (group.current) {
      group.current.scale.setScalar(breath * pulse);
      group.current.rotation.y = t * (0.15 + amplitude * 0.8);
      group.current.rotation.x = Math.sin(t * 0.4) * 0.08;
    }
    const glow = 0.35 + amplitude * 1.4;
    if (mat.current) {
      mat.current.emissive.copy(color);
      mat.current.emissiveIntensity = glow;
      mat.current.color.copy(color);
      mat.current.opacity = 0.55 + amplitude * 0.35;
    }
    if (lineMat.current) {
      lineMat.current.color.copy(color);
      lineMat.current.opacity = 0.25 + amplitude * 0.55;
    }
    invalidate();
  });

  return (
    <group ref={group}>
      <mesh>
        <icosahedronGeometry args={[1.05, 1]} />
        <meshStandardMaterial
          ref={mat}
          color={color}
          emissive={color}
          emissiveIntensity={0.4}
          transparent
          opacity={0.55}
          wireframe={false}
          roughness={0.35}
          metalness={0.2}
        />
      </mesh>
      <mesh>
        <icosahedronGeometry args={[1.08, 1]} />
        <meshBasicMaterial color={color} wireframe transparent opacity={0.2} />
      </mesh>
      <points>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        </bufferGeometry>
        <pointsMaterial color={color} size={0.045} sizeAttenuation transparent opacity={0.9} />
      </points>
      <lineSegments>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[linePositions, 3]} />
        </bufferGeometry>
        <lineBasicMaterial ref={lineMat} color={color} transparent opacity={0.3} />
      </lineSegments>
    </group>
  );
}
