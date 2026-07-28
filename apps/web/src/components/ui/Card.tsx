import type { ReactNode } from 'react';

export function Card({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-3xl border border-hair bg-panel p-5 backdrop-blur-md shadow-[var(--cp-shadow-soft)] ${className}`}
    >
      {children}
    </div>
  );
}

