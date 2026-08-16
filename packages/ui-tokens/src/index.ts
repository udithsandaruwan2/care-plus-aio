/**
 * Care Plus Medical Light — shared tokens for web (Tailwind) and mobile.
 * @see docs/FRONTEND.md §2
 */
export const colors = {
  bgVoid: '#F8FAFC',
  bgPanel: '#FFFFFF',
  borderHair: '#E2E8F0',
  accentCyan: '#0D9488',
  accentViolet: '#3B82F6',
  accentMint: '#10B981',
  accentAmber: '#F59E0B',
  accentRose: '#EF4444',
  textPrimary: '#0F172A',
  textMuted: '#475569',
} as const;

export const motion = {
  springSoft: { stiffness: 180, damping: 22 },
  durationFast: 150,
  durationBase: 260,
  durationSlow: 420,
} as const;

export const typography = {
  display: '"Inter", "Noto Sans Sinhala", "Noto Sans Tamil", system-ui, sans-serif',
  body: '"Inter", "Noto Sans Sinhala", "Noto Sans Tamil", system-ui, sans-serif',
} as const;

export const brand = {
  name: 'Care Plus',
  theme: 'Medical Light',
} as const;

export type ColorToken = keyof typeof colors;
