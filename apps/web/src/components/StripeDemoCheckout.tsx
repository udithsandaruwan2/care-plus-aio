import { FormEvent, useState } from 'react';
import { formatLkr } from '../lib/formatLkr';
import { formatCardNumber, formatExpiry, validateDemoCard } from '../payments/stripeDemo';

type Props = {
  amountLkr: string | number;
  email?: string;
  paying: boolean;
  onPay: () => Promise<void>;
  onDeclined: (message: string) => void;
};

/** Hosted-checkout lookalike. No Stripe.js and no card data sent to the API. */
export function StripeDemoCheckout({ amountLkr, email, paying, onPay, onDeclined }: Props) {
  const [number, setNumber] = useState('');
  const [expiry, setExpiry] = useState('');
  const [cvc, setCvc] = useState('');
  const [name, setName] = useState('');
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setFieldError(null);
    const check = validateDemoCard({ number, expiry, cvc, name });
    if (!check.ok) {
      setFieldError(check.message);
      if (check.decline) onDeclined(check.message);
      return;
    }
    setBusy(true);
    try {
      await new Promise((r) => setTimeout(r, 900));
      await onPay();
    } finally {
      setBusy(false);
    }
  }

  const disabled = paying || busy;
  const label = formatLkr(amountLkr);

  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#0a2540] shadow-[0_24px_80px_rgba(0,0,0,0.45)]">
      <div className="flex items-center justify-between px-5 py-4">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-[#635bff] text-[11px] font-bold text-white">
            S
          </span>
          <span className="text-sm font-semibold tracking-tight text-white">stripe</span>
        </div>
        <p className="text-xs text-white/60">Test mode</p>
      </div>

      <div className="bg-white px-5 py-6 text-[#30313d]">
        <p className="text-xs uppercase tracking-[0.14em] text-[#6d6e78]">Pay Care Plus</p>
        <p className="mt-1 text-3xl font-semibold tracking-tight">{label}</p>
        <p className="mt-1 text-sm text-[#6d6e78]">Home care package · LKR</p>

        <form onSubmit={onSubmit} className="mt-6 space-y-3" autoComplete="off">
          <label className="block text-[13px] font-medium">
            Email
            <input
              type="email"
              readOnly
              value={email ?? ''}
              className="mt-1 w-full rounded-md border border-[#e0e1e6] bg-[#f6f8fa] px-3 py-2.5 text-sm outline-none"
            />
          </label>

          <fieldset className="space-y-0">
            <legend className="mb-1 text-[13px] font-medium">Card information</legend>
            <input
              inputMode="numeric"
              autoComplete="cc-number"
              placeholder="1234 1234 1234 1234"
              value={number}
              onChange={(e) => setNumber(formatCardNumber(e.target.value))}
              className="w-full rounded-t-md border border-[#e0e1e6] px-3 py-2.5 text-sm outline-none focus:border-[#635bff] focus:ring-1 focus:ring-[#635bff]"
            />
            <div className="grid grid-cols-2">
              <input
                inputMode="numeric"
                autoComplete="cc-exp"
                placeholder="MM / YY"
                value={expiry}
                onChange={(e) => setExpiry(formatExpiry(e.target.value))}
                className="-mt-px border border-[#e0e1e6] px-3 py-2.5 text-sm outline-none focus:border-[#635bff] focus:ring-1 focus:ring-[#635bff]"
              />
              <input
                inputMode="numeric"
                autoComplete="cc-csc"
                placeholder="CVC"
                value={cvc}
                onChange={(e) => setCvc(e.target.value.replace(/\D/g, '').slice(0, 4))}
                className="-mt-px -ml-px border border-[#e0e1e6] px-3 py-2.5 text-sm outline-none focus:z-10 focus:border-[#635bff] focus:ring-1 focus:ring-[#635bff]"
              />
            </div>
          </fieldset>

          <label className="block text-[13px] font-medium">
            Cardholder name
            <input
              autoComplete="cc-name"
              placeholder="Full name on card"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-md border border-[#e0e1e6] px-3 py-2.5 text-sm outline-none focus:border-[#635bff] focus:ring-1 focus:ring-[#635bff]"
            />
          </label>

          {fieldError && (
            <p className="rounded-md bg-[#fdecec] px-3 py-2 text-sm text-[#df1b41]">{fieldError}</p>
          )}

          <button
            type="submit"
            disabled={disabled}
            className="w-full rounded-md bg-[#635bff] py-3 text-sm font-semibold text-white transition hover:bg-[#5851ea] disabled:opacity-60"
          >
            {disabled ? 'Processing…' : `Pay ${label}`}
          </button>
        </form>

        <p className="mt-4 text-center text-[11px] text-[#6d6e78]">
          Powered by stripe · Demo gateway — use{' '}
          <span className="font-mono">4242 4242 4242 4242</span>
        </p>
      </div>
    </div>
  );
}
