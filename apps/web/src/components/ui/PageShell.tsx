import type { ReactNode } from 'react';

export function PageShell({
  children,
  className = 'mx-auto flex min-h-full max-w-6xl flex-col px-5 py-8 sm:px-8',
}: {
  children: ReactNode;
  className?: string;
}) {
  return <main className={className}>{children}</main>;
}
