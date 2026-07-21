import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import type { Order } from '@care-plus/api-client';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { OrderSummary } from '../components/OrderSummary';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';

/** Post-payment success — care relationship is active after paid order. */
export function OrderSuccessPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const { logout } = useAuth();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const id = Number(orderId);

  useEffect(() => {
    if (!Number.isFinite(id)) return;
    api
      .getOrder(id)
      .then(setOrder)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load order.'));
  }, [id]);

  return (
    <AtmosphereShell>
      <main className="mx-auto flex min-h-full max-w-3xl flex-col px-6 py-10">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-display text-sm uppercase tracking-[0.2em] text-mint">Paid</p>
            <h1 className="mt-2 font-display text-3xl font-semibold text-mist">Payment successful</h1>
            <p className="mt-2 text-sm text-muted">
              Your care link is now active. Your caregiver has been marked unavailable for new
              matches while this relationship continues.
            </p>
          </div>
          <button
            type="button"
            onClick={logout}
            className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted hover:border-rose hover:text-rose"
          >
            Sign out
          </button>
        </div>

        {error && (
          <p className="mt-8 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
            {error}
          </p>
        )}

        {order && (
          <div className="mt-8">
            <OrderSummary order={order} />
          </div>
        )}

        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            to="/"
            className="rounded-lg border border-mint/50 px-4 py-2.5 text-sm text-mint transition hover:bg-mint/10"
          >
            Neural Core
          </Link>
          <Link
            to="/requests"
            className="rounded-lg border border-hair px-4 py-2.5 text-sm text-muted hover:border-cyan hover:text-cyan"
          >
            Care requests
          </Link>
        </div>
      </main>
    </AtmosphereShell>
  );
}
