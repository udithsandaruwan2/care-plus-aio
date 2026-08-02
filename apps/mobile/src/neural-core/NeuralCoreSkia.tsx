import { useEffect, useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import {
  Canvas,
  Circle,
  Group,
  BlurMask,
  vec,
} from '@shopify/react-native-skia';
import {
  useSharedValue,
  useDerivedValue,
  withRepeat,
  withTiming,
  Easing,
  cancelAnimation,
} from 'react-native-reanimated';
import { AssistantState } from '@care-plus/core';
import { colors } from '@care-plus/ui-tokens';

const STATE_COLOR: Record<AssistantState, string> = {
  [AssistantState.IDLE]: colors.accentCyan,
  [AssistantState.LISTENING]: colors.accentCyan,
  [AssistantState.THINKING]: colors.accentViolet,
  [AssistantState.CLARIFYING]: colors.accentViolet,
  [AssistantState.SPEAKING]: colors.accentAmber,
  [AssistantState.CHAT_REPLY]: colors.accentMint,
  [AssistantState.MATCHING]: colors.accentViolet,
  [AssistantState.RESULTS]: colors.accentMint,
  [AssistantState.EMERGENCY]: colors.accentRose,
};

const PARTICLE_COUNT = 220;
const SIZE = 260;

function mulberry32(seed: number) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

type Props = {
  state: AssistantState;
  /** 0–1 pulse strength (listening / thinking). */
  amplitude?: number;
};

/** Lean Skia neuron cloud — Aurora Neural state colors + soft pulse. */
export function NeuralCoreSkia({ state, amplitude = 0.25 }: Props) {
  const color = STATE_COLOR[state] ?? colors.accentCyan;
  const pulse = useSharedValue(0.85);
  const active =
    state === AssistantState.LISTENING ||
    state === AssistantState.THINKING ||
    state === AssistantState.MATCHING ||
    state === AssistantState.EMERGENCY;

  useEffect(() => {
    if (active) {
      pulse.value = withRepeat(
        withTiming(1.12, { duration: 900, easing: Easing.inOut(Easing.sin) }),
        -1,
        true,
      );
    } else {
      cancelAnimation(pulse);
      pulse.value = withTiming(0.92 + amplitude * 0.15, { duration: 280 });
    }
  }, [active, amplitude, pulse]);

  const particles = useMemo(() => {
    const rand = mulberry32(42);
    const pts: { x: number; y: number; r: number }[] = [];
    const cx = SIZE / 2;
    const cy = SIZE / 2;
    const radius = SIZE * 0.38;
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      // Fibonacci-ish disk
      const a = rand() * Math.PI * 2;
      const d = Math.sqrt(rand()) * radius;
      pts.push({
        x: cx + Math.cos(a) * d,
        y: cy + Math.sin(a) * d * 0.92,
        r: 1.1 + rand() * 1.8,
      });
    }
    return pts;
  }, []);

  const transform = useDerivedValue(() => {
    const s = pulse.value;
    const c = SIZE / 2;
    return [{ translateX: c }, { translateY: c }, { scale: s }, { translateX: -c }, { translateY: -c }];
  });

  return (
    <View style={styles.wrap}>
      <Canvas style={styles.canvas}>
        <Group transform={transform}>
          <Circle c={vec(SIZE / 2, SIZE / 2)} r={SIZE * 0.22} color={color} opacity={0.12}>
            <BlurMask blur={28} style="normal" />
          </Circle>
          {particles.map((p, i) => (
            <Circle key={i} cx={p.x} cy={p.y} r={p.r} color={color} opacity={0.55 + (i % 5) * 0.08} />
          ))}
          <Circle c={vec(SIZE / 2, SIZE / 2)} r={SIZE * 0.08} color={color} opacity={0.85}>
            <BlurMask blur={10} style="solid" />
          </Circle>
        </Group>
      </Canvas>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  canvas: {
    width: SIZE,
    height: SIZE,
  },
});
