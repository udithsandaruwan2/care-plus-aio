import type { ReactNode } from 'react';

export function PageHeader({
  title,
  subtitle,
  actions,
  eyebrow,
}: {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && (
          <p className="hidden font-display text-sm uppercase tracking-[0.2em] text-cyan lg:block">
            {eyebrow}
          </p>
        )}
        <h1 className={`font-display text-xl text-mist lg:text-3xl ${eyebrow ? 'mt-1 lg:mt-2' : ''}`}>
          {title}
        </h1>
        {subtitle && <p className="mt-1 hidden max-w-2xl text-sm text-muted lg:block">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
