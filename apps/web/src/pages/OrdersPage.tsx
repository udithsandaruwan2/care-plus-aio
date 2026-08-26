import { useEffect, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import type { Order } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { PageHeader } from '../components/ui/PageHeader';

const STATUS_LABEL: Record<string, string> = {
  awaiting_payment: 'Awaiting payment',
  paid: 'Paid',
  cancelled: 'Cancelled',
  expired: 'Expired',
};

export function OrdersPage() {
  const { user } = useAuth();
  const [rows, setRows] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user?.role !== 'patient') {
      setLoading(false);
      return;
    }
    setLoading(true);
    api
      .listOrders()
      .then(setRows)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load orders.'))
      .finally(() => setLoading(false));
  }, [user?.role]);

  if (user && user.role !== 'patient') {
    return <Navigate to="/hub" replace />;
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col">
      <PageHeader
        eyebrow="Billing"
        title="Orders"
        subtitle="Resume unpaid checkouts or open receipts for paid care packages."
      />
      {loading ? <p className="mt-6 text-sm text-muted">Loading orders…</p> : null}
      {error ? (
        <p className="mt-6 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
          {error}
        </p>
      ) : null}
      {!loading && !error && rows.length === 0 ? (
        <p className="mt-6 text-sm text-muted">No orders yet. Accept a care request, then checkout.</p>
      ) : null}
      <ul className="mt-6 space-y-3">
        {rows.map((order) => {
          const total = String(order.total_lkr);
          const status = STATUS_LABEL[order.status] || order.status;
          const unpaid = order.status === 'awaiting_payment';
          return (
            <li
              key={order.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-hair bg-panel px-4 py-3"
            >
              <div>
                <p className="font-display text-sm text-mist">Order #{order.id}</p>
                <p className="text-xs text-muted">
                  {status} · LKR {total} · {new Date(order.created_at).toLocaleString()}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {unpaid ? (
                  <Link
                    to={`/orders/${order.id}/pay`}
                    className="rounded-lg bg-cyan px-3 py-1.5 text-xs font-semibold text-inverse"
                  >
                    Pay
                  </Link>
                ) : null}
                {order.status === 'paid' ? (
                  <Link
                    to={`/orders/${order.id}/success`}
                    className="rounded-lg border border-hair px-3 py-1.5 text-xs text-muted hover:border-cyan hover:text-cyan"
                  >
                    Receipt
                  </Link>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
