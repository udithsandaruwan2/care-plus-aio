import { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
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
  [S.CHAT_REPLY]: colors.accentMint,
  [S.MATCHING]: colors.accentViolet,
  [S.RESULTS]: colors.accentMint,
  [S.EMERGENCY]: colors.accentRose,
};

const SHELL_COUNT = 96;
const HUB_COUNT = 8;
const LONG_RANGE = 10;
const PULSE_COUNT = 12;
const GOLDEN = Math.PI * (3 - Math.sqrt(5));

type NeuralMeshProps = {
  amplitude: number;
  state: AssistantState;
  /** When false, skip continuous animation (idle static frame). */
  animate: boolean;
  /** Stage fills a pane; well is the tighter public hero. */
  spread?: number;
  /** Light = public white page (normal blend). Dark = Serah slate well (additive). */
  surface?: 'dark' | 'light';
};

type Neuron = {
  pos: THREE.Vector3;
  radius: number;
  hub: boolean;
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

function buildConnectome(spread: number) {
  const rand = mulberry32(20260718);
  const radius = 1.08 * spread;
  const neurons: Neuron[] = [];

  for (let i = 0; i < SHELL_COUNT; i++) {
    const y = 1 - (i / (SHELL_COUNT - 1)) * 2;
    const rxy = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = GOLDEN * i;
    const jitter = 0.035 * (rand() - 0.5);
    const r = radius * (0.9 + rand() * 0.1);
    neurons.push({
      pos: new THREE.Vector3(
        Math.cos(theta) * rxy * r + jitter,
        y * r,
        Math.sin(theta) * rxy * r,
      ),
      radius: i % 7 === 0 ? 0.04 : 0.024,
      hub: false,
    });
  }

  for (let i = 0; i < HUB_COUNT; i++) {
    const u = rand();
    const v = rand();
    const theta = Math.acos(2 * u - 1);
    const phi = 2 * Math.PI * v;
    const r = radius * (0.1 + 0.28 * rand());
    neurons.push({
      pos: new THREE.Vector3(
        r * Math.sin(theta) * Math.cos(phi),
        r * Math.sin(theta) * Math.sin(phi),
        r * Math.cos(theta),
      ),
      radius: 0.056,
      hub: true,
    });
  }

  const edges: Array<[number, number]> = [];
  const seen = new Set<string>();
  const addEdge = (a: number, b: number) => {
    if (a === b) return;
    const key = a < b ? `${a}-${b}` : `${b}-${a}`;
    if (seen.has(key)) return;
    seen.add(key);
    edges.push([a, b]);
  };

  for (let i = 0; i < neurons.length; i++) {
    const dists: Array<{ j: number; d: number }> = [];
    for (let j = 0; j < neurons.length; j++) {
      if (i === j) continue;
      dists.push({ j, d: neurons[i].pos.distanceToSquared(neurons[j].pos) });
    }
    dists.sort((a, b) => a.d - b.d);
    const k = neurons[i].hub ? 4 : 2 + (i % 2);
    for (let n = 0; n < k && n < dists.length; n++) addEdge(i, dists[n].j);
  }

  let longRange = 0;
  let guard = 0;
  const minLong = (radius * 0.85) ** 2;
  while (longRange < LONG_RANGE && guard < 120) {
    guard += 1;
    const a = Math.floor(rand() * neurons.length);
    const b = Math.floor(rand() * neurons.length);
    if (neurons[a].pos.distanceToSquared(neurons[b].pos) < minLong) continue;
    const before = edges.length;
    addEdge(a, b);
    if (edges.length > before) longRange += 1;
  }

  const linePositions = new Float32Array(edges.length * 6);
  edges.forEach(([a, b], i) => {
    const o = i * 6;
    linePositions[o] = neurons[a].pos.x;
    linePositions[o + 1] = neurons[a].pos.y;
    linePositions[o + 2] = neurons[a].pos.z;
    linePositions[o + 3] = neurons[b].pos.x;
    linePositions[o + 4] = neurons[b].pos.y;
    linePositions[o + 5] = neurons[b].pos.z;
  });

  const pulseEdges = Array.from({ length: PULSE_COUNT }, (_, i) => {
    const edge = edges[Math.floor(rand() * edges.length)] ?? edges[0] ?? [0, 1];
    return { a: edge[0], b: edge[1], offset: (i / PULSE_COUNT + rand() * 0.12) % 1 };
  });

  return { neurons, linePositions, pulseEdges };
}

/**
 * Sparse 3D connectome: hub neurons, local synapses, long-range axons, traveling pulses.
 * Additive materials only — no Bloom pass (that painted a square on the canvas).
 */
export function NeuralMesh({
  amplitude,
  state,
  animate,
  spread = 1,
  surface = 'dark',
}: NeuralMeshProps) {
  const group = useRef<THREE.Group>(null);
  const nodeMesh = useRef<THREE.InstancedMesh>(null);
  const pulseMesh = useRef<THREE.InstancedMesh>(null);
  const lineMat = useRef<THREE.LineBasicMaterial>(null);
  const hazeMat = useRef<THREE.MeshBasicMaterial>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const { invalidate } = useThree();
  const color = useMemo(() => new THREE.Color(STATE_COLOR[state]), [state]);

  const { neurons, linePositions, pulseEdges } = useMemo(
    () => buildConnectome(spread),
    [spread],
  );

  const additive = surface === 'dark';
  const nodeGeo = useMemo(() => new THREE.SphereGeometry(1, 10, 10), []);
  const nodeMat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: STATE_COLOR[S.IDLE],
        transparent: true,
        opacity: additive ? 0.92 : 0.88,
        depthWrite: false,
        blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
      }),
    [additive],
  );
  const pulseGeo = useMemo(() => new THREE.SphereGeometry(1, 8, 8), []);
  const pulseMat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: STATE_COLOR[S.IDLE],
        transparent: true,
        opacity: additive ? 0.95 : 0.9,
        depthWrite: false,
        blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
      }),
    [additive],
  );

  useEffect(() => {
    return () => {
      nodeGeo.dispose();
      nodeMat.dispose();
      pulseGeo.dispose();
      pulseMat.dispose();
    };
  }, [nodeGeo, nodeMat, pulseGeo, pulseMat]);

  useLayoutEffect(() => {
    const mesh = nodeMesh.current;
    if (!mesh) return;
    neurons.forEach((n, i) => {
      dummy.position.copy(n.pos);
      dummy.scale.setScalar(n.radius);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    });
    mesh.instanceMatrix.needsUpdate = true;

    const pulses = pulseMesh.current;
    if (!pulses) return;
    pulseEdges.forEach((p, i) => {
      const from = neurons[p.a]?.pos;
      const to = neurons[p.b]?.pos;
      if (!from || !to) return;
      dummy.position.lerpVectors(from, to, p.offset);
      dummy.scale.setScalar(0.018);
      dummy.updateMatrix();
      pulses.setMatrixAt(i, dummy.matrix);
    });
    pulses.instanceMatrix.needsUpdate = true;
  }, [dummy, neurons, pulseEdges]);

  const spinVel = useRef(0.16);

  useFrame(({ clock }, delta) => {
    if (!animate) return;
    const t = clock.getElapsedTime();
    const dt = Math.min(delta, 0.05);
    const amp = Math.min(amplitude, 0.7);
    const live = 0.16 + amp;
    const breath = 1 + Math.sin(t * 1.05) * 0.035;
    const ampPulse = 1 + amp * 0.18;
    const fire = 0.5 + 0.5 * Math.sin(t * (2.2 + amp * 5));
    const thinking =
      state === S.THINKING || state === S.MATCHING || state === S.CLARIFYING;
    const speaking = state === S.SPEAKING || state === S.CHAT_REPLY;
    const emergency = state === S.EMERGENCY;
    const targetSpin =
      0.16 + amp * 0.38 + (thinking ? 0.26 : 0) + (speaking ? 0.1 : 0) + (emergency ? 0.42 : 0);
    spinVel.current += (targetSpin - spinVel.current) * Math.min(1, dt * 3.2);

    if (group.current) {
      group.current.scale.setScalar(breath * ampPulse);
      group.current.rotation.y += dt * spinVel.current;
      group.current.rotation.x = Math.sin(t * 0.38) * 0.12;
      group.current.rotation.z = Math.cos(t * 0.26) * 0.05;
    }

    const nodes = nodeMesh.current;
    if (nodes) {
      nodeMat.color.copy(color);
      nodeMat.opacity = 0.78 + live * 0.18 + fire * 0.06;
      neurons.forEach((n, i) => {
        const dist = n.pos.length();
        const wave = speaking ? 1 + Math.sin(t * 3.1 - dist * 3.6) * 0.14 : 1;
        const listen = 1 + amp * (n.hub ? 0.28 : 0.16);
        dummy.position.copy(n.pos);
        dummy.scale.setScalar(n.radius * listen * wave);
        dummy.updateMatrix();
        nodes.setMatrixAt(i, dummy.matrix);
      });
      nodes.instanceMatrix.needsUpdate = true;
    }

    if (lineMat.current) {
      lineMat.current.color.copy(color);
      lineMat.current.opacity = additive
        ? 0.22 + live * 0.28 + (thinking ? 0.12 : 0)
        : 0.38 + live * 0.22 + (thinking ? 0.1 : 0);
    }
    if (hazeMat.current) {
      hazeMat.current.color.copy(color);
      hazeMat.current.opacity = additive ? 0.05 + amp * 0.08 : 0.04 + amp * 0.03;
    }

    const pulses = pulseMesh.current;
    if (pulses) {
      pulseMat.color.copy(color);
      const speed = 0.18 + amp * 0.55 + (thinking ? 0.35 : 0) + (emergency ? 0.55 : 0);
      pulseEdges.forEach((p, i) => {
        const from = neurons[p.a]?.pos;
        const to = neurons[p.b]?.pos;
        if (!from || !to) return;
        const u = (p.offset + t * speed) % 1;
        dummy.position.lerpVectors(from, to, u);
        dummy.scale.setScalar(0.018 + amp * 0.012 + fire * 0.006);
        dummy.updateMatrix();
        pulses.setMatrixAt(i, dummy.matrix);
      });
      pulses.instanceMatrix.needsUpdate = true;
    }

    invalidate();
  });

  return (
    <group ref={group}>
      {additive ? (
        <mesh>
          <sphereGeometry args={[0.62 * spread, 24, 24]} />
          <meshBasicMaterial
            ref={hazeMat}
            color={color}
            transparent
            opacity={0.07}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      ) : null}

      <instancedMesh
        ref={nodeMesh}
        args={[nodeGeo, nodeMat, neurons.length]}
        frustumCulled={false}
      />

      <lineSegments>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[linePositions, 3]} />
        </bufferGeometry>
        <lineBasicMaterial
          ref={lineMat}
          color={color}
          transparent
          opacity={additive ? 0.34 : 0.42}
          depthWrite={false}
          blending={additive ? THREE.AdditiveBlending : THREE.NormalBlending}
        />
      </lineSegments>

      <instancedMesh
        ref={pulseMesh}
        args={[pulseGeo, pulseMat, PULSE_COUNT]}
        frustumCulled={false}
      />
    </group>
  );
}
