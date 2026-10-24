import type { ReactNode } from 'react';
import { Card } from './Card';

export function StatCard({
  icon,
  title,
  value,
  subtitle,
  highlight = false,
}: {
  icon: ReactNode;
  title: string;
  value: string;
  subtitle?: string;
  highlight?: boolean;
}) {
  return (
    <Card className={highlight ? 'border-cyan/30 ring-1 ring-cyan/20' : ''}>
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-cyan/10 text-cyan sm:h-10 sm:w-10">
          {icon}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted sm:text-xs">{title}</p>
          <p className="mt-0.5 font-display text-xl font-bold text-mist sm:mt-1 sm:text-2xl">{value}</p>
          {subtitle && <p className="mt-1 hidden text-xs text-muted sm:block">{subtitle}</p>}
        </div>
      </div>
    </Card>
  );
}
