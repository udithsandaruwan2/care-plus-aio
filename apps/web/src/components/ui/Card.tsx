import type { ReactNode } from 'react';

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-2xl border border-hair bg-panel p-5 shadow-[var(--cp-shadow-soft)] ${className}`}
    >
      {children}
    </div>
  );
}
