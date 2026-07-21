import type { Order } from '@care-plus/api-client';
import { formatLkr } from '../lib/formatLkr';

type Props = {
  order: Order;
};

/** Line-item + total breakdown for checkout / pay pages. */
export function OrderSummary({ order }: Props) {
  return (
    <div className="rounded-2xl border border-hair bg-panel/70 p-5 backdrop-blur-md">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-display text-lg text-mist">Order #{order.id}</p>
          <p className="mt-1 text-xs uppercase tracking-wide text-muted">
            {order.status.replace(/_/g, ' ')} · {order.days} day{order.days === 1 ? '' : 's'}
          </p>
        </div>
        <p className="font-mono text-lg text-mint">{formatLkr(order.total_lkr)}</p>
      </div>
      <ul className="mt-4 space-y-2 border-t border-hair pt-4">
        {order.lines.map((line) => (
          <li key={line.id} className="flex flex-wrap items-start justify-between gap-2 text-sm">
            <div>
              <p className="text-mist/90">{line.name}</p>
              <p className="text-xs text-muted">
                {line.kind === 'package'
                  ? `${formatLkr(line.unit_price_lkr)} × ${line.quantity} days`
                  : 'Add-on'}
              </p>
            </div>
            <p className="font-mono text-mint">{formatLkr(line.line_total_lkr)}</p>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex items-center justify-between border-t border-hair pt-4">
        <p className="text-sm text-muted">Total ({order.currency})</p>
        <p className="font-mono text-mint">{formatLkr(order.total_lkr)}</p>
      </div>
    </div>
  );
}
