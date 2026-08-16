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
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan/10 text-cyan">
          {icon}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</p>
          <p className="mt-1 font-display text-2xl font-bold text-mist">{value}</p>
          {subtitle && <p className="mt-1 text-xs text-muted">{subtitle}</p>}
        </div>
      </div>
    </Card>
  );
}
