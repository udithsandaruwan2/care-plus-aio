import type { ReactNode } from 'react';
import { colors } from '@care-plus/ui-tokens';

export function AtmosphereShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-full overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background: `
            radial-gradient(ellipse 80% 50% at 20% 10%, ${colors.accentViolet}22, transparent 55%),
            radial-gradient(ellipse 60% 40% at 85% 20%, ${colors.accentCyan}18, transparent 50%),
            radial-gradient(ellipse 50% 60% at 50% 100%, ${colors.accentMint}10, transparent 45%),
            ${colors.bgVoid}
          `,
        }}
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
}
