import type { ReactNode } from 'react';
import { AtmosphereShell } from '../AtmosphereShell';
import { AIAssistantDock } from '../layout/AIAssistantDock';

export function PageShell({
  children,
  className = 'mx-auto flex min-h-full max-w-6xl flex-col px-5 py-8 sm:px-8',
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <AtmosphereShell>
      <main className={className}>{children}</main>
      <AIAssistantDock />
    </AtmosphereShell>
  );
}

