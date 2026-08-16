import type { ReactNode } from 'react';

export function PublicPage({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`mx-auto w-full max-w-6xl px-6 py-10 ${className}`}>{children}</div>;
}
