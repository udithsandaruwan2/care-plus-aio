/**
 * Aurora Neural design tokens — single source for web (Tailwind) and mobile.
 * @see docs/FRONTEND.md §2
 */
export const colors = {
  bgVoid: '#05060A',
  bgPanel: 'rgba(18, 22, 34, 0.6)',
  borderHair: 'rgba(148, 163, 184, 0.14)',
  accentCyan: '#22D3EE',
  accentViolet: '#8B5CF6',
  accentMint: '#34D399',
  accentAmber: '#F59E0B',
  accentRose: '#FB7185',
  textPrimary: '#E5EDFF',
  textMuted: '#8A94AD',
} as const;

export const motion = {
  springSoft: { stiffness: 180, damping: 22 },
  durationFast: 150,
  durationBase: 260,
  durationSlow: 420,
} as const;

export const typography = {
  display: '"Space Grotesk", "Sora", system-ui, sans-serif',
  body: '"Inter", "Noto Sans Sinhala", "Noto Sans Tamil", system-ui, sans-serif',
} as const;

export const brand = {
  name: 'Care Plus',
  theme: 'Aurora Neural',
} as const;

export type ColorToken = keyof typeof colors;
