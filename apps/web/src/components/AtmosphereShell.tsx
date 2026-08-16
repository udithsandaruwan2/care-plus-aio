import type { ReactNode } from 'react';

export function AtmosphereShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-full overflow-hidden bg-void">
      <div className="relative z-10">{children}</div>
    </div>
  );
}
