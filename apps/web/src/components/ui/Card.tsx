import type { ReactNode } from 'react';

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-2xl border border-hair bg-panel p-3 shadow-[var(--cp-shadow-soft)] sm:p-5 ${className}`}
    >
      {children}
    </div>
  );
}
