import { GOAL_FIELDS, type IntentDraft } from '@care-plus/core';
import { colors } from '@care-plus/ui-tokens';

const FIELD_COLOR: Record<(typeof GOAL_FIELDS)[number], string> = {
  condition: colors.accentCyan,
  language: colors.accentViolet,
  care_level: colors.accentMint,
};

type Props = {
  intent: IntentDraft;
  size?: number;
  children?: React.ReactNode;
};

/**
 * Circular progress ring — one arc segment per required intent field.
 * A segment lights up (and gains color) once its field is captured.
 */
export function GoalRing({ intent, size = 288, children }: Props) {
  const stroke = 6;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const n = GOAL_FIELDS.length;
  const gap = 0.06 * c; // gap between segments
  const seg = c / n - gap;

  // Keep the Neural Core inside a circular mask so any canvas clear/glow
  // can't read as a square when the brain lights up.
  const inset = stroke + 4;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="absolute inset-0 -rotate-90" aria-hidden>
        {GOAL_FIELDS.map((field, i) => {
          const filled = Boolean(intent[field]);
          const offset = -(i * (seg + gap));
          return (
            <circle
              key={field}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={filled ? FIELD_COLOR[field] : colors.borderHair}
              strokeWidth={stroke}
              strokeLinecap="round"
              strokeDasharray={`${seg} ${c - seg}`}
              strokeDashoffset={offset}
              style={{
                transition: 'stroke 400ms ease',
                filter: filled ? `drop-shadow(0 0 6px ${FIELD_COLOR[field]})` : 'none',
              }}
            />
          );
        })}
      </svg>
      <div
        className="absolute overflow-hidden rounded-full"
        style={{ inset, background: 'transparent' }}
      >
        {children}
      </div>
    </div>
  );
}
