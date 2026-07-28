import type { ReactNode } from 'react';

export function AtmosphereShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-full overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background: `
            radial-gradient(ellipse 80% 50% at 20% 10%, color-mix(in oklab, var(--cp-accent-violet) 20%, transparent), transparent 55%),
            radial-gradient(ellipse 60% 40% at 85% 20%, color-mix(in oklab, var(--cp-accent-cyan) 16%, transparent), transparent 50%),
            radial-gradient(ellipse 50% 60% at 50% 100%, color-mix(in oklab, var(--cp-accent-mint) 12%, transparent), transparent 45%),
            var(--cp-bg-void)
          `,
        }}
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
}
