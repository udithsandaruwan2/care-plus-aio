import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import type { PaymentIntent } from '@care-plus/api-client';
import { api } from '../auth/api';
import { PageHeader } from '../components/ui/PageHeader';

/** Payment failure / incomplete — retry path back to pay. */
export function OrderFailedPage() {
  const { orderId } = useParams<{ orderId: string }>();
  
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
    <div className="mx-auto flex w-full max-w-3xl flex-col">
        <PageHeader
        eyebrow="Payment"
        title="Payment not completed"
        subtitle="Payment didn’t complete. Your order is unpaid — you can retry PayHere when ready."
      />

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
      </div>
  );
}
