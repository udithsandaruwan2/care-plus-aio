import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import type { Order, PaymentIntent } from '@care-plus/api-client';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { OrderSummary } from '../components/OrderSummary';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';

/** Order summary + mock / PayHere pay CTA (Step 32). No fake card fields in mock mode. */
export function OrderPayPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [order, setOrder] = useState<Order | null>(null);
  const [intent, setIntent] = useState<PaymentIntent | null>(null);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const id = Number(orderId);

  const load = useCallback(async () => {
    if (!Number.isFinite(id)) {
      setError('Invalid order.');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const o = await api.getOrder(id);
      setOrder(o);
      if (o.status === 'paid') {
        navigate(`/orders/${id}/success`, { replace: true });
        return;
      }
      let pi: PaymentIntent;
      try {
        pi = await api.getPaymentIntent(id);
      } catch {
        pi = await api.createPaymentIntent(id);
      }
      if (pi.status === 'succeeded') {
        navigate(`/orders/${id}/success`, { replace: true });
        return;
      }
      if (pi.status === 'failed') {
        navigate(`/orders/${id}/failed`, { replace: true });
        return;
      }
      setIntent(pi);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load order.');
    } finally {
      setLoading(false);
    }
  }, [id, navigate]);

  useEffect(() => {
    if (user?.role === 'patient') {
      void load();
    } else {
      setLoading(false);
    }
  }, [user?.role, load]);

  async function onMockPay() {
    if (!intent) return;
    setPaying(true);
    setError(null);
    try {
      const confirmed = await api.confirmMockPayment(intent.provider_intent_id);
      if (confirmed.status === 'succeeded') {
        navigate(`/orders/${id}/success`);
      } else {
        navigate(`/orders/${id}/failed`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Payment confirmation failed.');
      navigate(`/orders/${id}/failed`);
    } finally {
      setPaying(false);
    }
  }

  const mode = (intent?.client_payload?.mode as string | undefined) ?? intent?.provider;

  return (
    <AtmosphereShell>
      <main className="mx-auto flex min-h-full max-w-3xl flex-col px-6 py-10">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-display text-sm uppercase tracking-[0.2em] text-cyan">Payment</p>
            <h1 className="mt-2 font-display text-3xl font-semibold text-mist">Pay for care</h1>
            <p className="mt-2 text-sm text-muted">
              Review your order, then confirm payment. No card details needed in mock mode.
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              to="/requests"
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted hover:border-cyan hover:text-cyan"
            >
              Requests
            </Link>
            <button
              type="button"
              onClick={logout}
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted hover:border-rose hover:text-rose"
            >
              Sign out
            </button>
          </div>
        </div>

        {user?.role !== 'patient' && (
          <p className="mt-8 text-sm text-muted">Only patients can pay for care orders.</p>
        )}

        {loading && <p className="mt-8 text-sm text-muted">Loading order…</p>}
        {error && (
          <p className="mt-8 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
            {error}
          </p>
        )}

        {order && (
          <div className="mt-8 space-y-6">
            <OrderSummary order={order} />

            {mode === 'mock' && (
              <div className="rounded-2xl border border-amber/40 bg-amber/5 p-5">
                <p className="text-sm text-amber">
                  Development mock payment — confirms instantly without card numbers.
                </p>
                <button
                  type="button"
                  disabled={paying || !intent}
                  onClick={() => void onMockPay()}
                  className="mt-4 rounded-lg border border-mint/50 px-4 py-2.5 text-sm text-mint transition hover:bg-mint/10 disabled:opacity-50"
                >
                  {paying ? 'Confirming…' : 'Confirm payment'}
                </button>
              </div>
            )}

            {mode === 'payhere' && intent && (
              <div className="rounded-2xl border border-cyan/40 bg-cyan/5 p-5">
                <p className="text-sm text-mist/90">
                  PayHere checkout is stubbed. Complete payment via the provider notify webhook in
                  staging; live redirect lands in a later release.
                </p>
                <p className="mt-2 font-mono text-xs text-muted">
                  order_id: {String(intent.client_payload?.order_id ?? intent.provider_intent_id)}
                </p>
                <Link
                  to={`/orders/${id}/failed`}
                  className="mt-4 inline-block text-sm text-cyan hover:underline"
                >
                  Payment not completed?
                </Link>
              </div>
            )}
          </div>
        )}
      </main>
    </AtmosphereShell>
  );
}
