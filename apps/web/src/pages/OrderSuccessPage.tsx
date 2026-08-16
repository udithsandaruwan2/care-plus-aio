import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import type { Order } from '@care-plus/api-client';
import { OrderSummary } from '../components/OrderSummary';
import { api } from '../auth/api';
import { PageHeader } from '../components/ui/PageHeader';
/** Post-payment success — care relationship is active after paid order. */
export function OrderSuccessPage() {
  const { orderId } = useParams<{ orderId: string }>();

  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openingReceipt, setOpeningReceipt] = useState(false);
  const id = Number(orderId);

  useEffect(() => {
    if (!Number.isFinite(id)) return;
    api
      .getOrder(id)
      .then(setOrder)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load order.'));
  }, [id]);

  async function openReceipt() {
    setOpeningReceipt(true);
    try {
      const html = await api.getOrderReceiptHtml(id);
      const blob = new Blob([html], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener,noreferrer');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open receipt.');
    } finally {
      setOpeningReceipt(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col">
      <PageHeader
        eyebrow="Paid"
        title="Payment successful"
        subtitle="Your care link is now active. A receipt with the LKR breakdown has been emailed to you."
      />

      {error && (
        <p className="mt-8 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
          {error}
        </p>
      )}

      {order && (
        <div className="mt-8">
          <OrderSummary order={order} />
          {order.receipt_email_sent && (
            <p className="mt-3 text-xs text-mint">Receipt emailed to your account address.</p>
          )}
        </div>
      )}

      <div className="mt-8 flex flex-wrap gap-3">
        <Link
          to="/hub"
          className="rounded-lg border border-mint/50 px-4 py-2.5 text-sm text-mint transition hover:bg-mint/10"
        >
          Open hub
        </Link>
        <button
          type="button"
          disabled={openingReceipt || !Number.isFinite(id)}
          onClick={() => void openReceipt()}
          className="rounded-lg border border-cyan/50 px-4 py-2.5 text-sm text-cyan transition hover:bg-cyan/10 disabled:opacity-50"
        >
          {openingReceipt ? 'Opening…' : 'View receipt'}
        </button>
        <Link
          to="/messages"
          className="rounded-lg border border-hair px-4 py-2.5 text-sm text-muted hover:border-cyan hover:text-cyan"
        >
          Messages
        </Link>
        <Link
          to="/requests"
          className="rounded-lg border border-hair px-4 py-2.5 text-sm text-muted hover:border-cyan hover:text-cyan"
        >
          Care requests
        </Link>
      </div>
    </div>
  );
}
