import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import type { PaymentIntent } from '@care-plus/api-client';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';

/** Payment failure / incomplete — retry path back to pay. */
export function OrderFailedPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const { logout } = useAuth();
  const [intent, setIntent] = useState<PaymentIntent | null>(null);
  const id = Number(orderId);

  useEffect(() => {
    if (!Number.isFinite(id)) return;
    api
      .getPaymentIntent(id)
      .then(setIntent)
      .catch(() => setIntent(null));
  }, [id]);

  return (
    <AtmosphereShell>
      <main className="mx-auto flex min-h-full max-w-3xl flex-col px-6 py-10">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-display text-sm uppercase tracking-[0.2em] text-rose">Failed</p>
            <h1 className="mt-2 font-display text-3xl font-semibold text-mist">Payment not completed</h1>
            <p className="mt-2 text-sm text-muted">
              Your order is still awaiting payment. You can try again when ready.
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

        {intent?.failure_message && (
          <p className="mt-8 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
            {intent.failure_code ? `${intent.failure_code}: ` : ''}
            {intent.failure_message}
          </p>
        )}

        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            to={`/orders/${id}/pay`}
            className="rounded-lg border border-mint/50 px-4 py-2.5 text-sm text-mint transition hover:bg-mint/10"
          >
            Try again
          </Link>
          <Link
            to="/requests"
            className="rounded-lg border border-hair px-4 py-2.5 text-sm text-muted hover:border-cyan hover:text-cyan"
          >
            Back to requests
          </Link>
        </div>
      </main>
    </AtmosphereShell>
  );
}
