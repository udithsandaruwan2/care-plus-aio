import { FormEvent, useEffect, useRef, useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { ApiError, userNeedsOtp } from '@care-plus/api-client';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { PageHeader } from '../components/ui/PageHeader';

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const body = err.body as { detail?: string } | null;
    if (typeof body?.detail === 'string') return body.detail;
    return `Request failed (${err.status}).`;
  }
  return 'Something went wrong. Try again.';
}

export function OtpPage() {
  const { user, requestOtp, verifyOtp } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? '/platform';
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [demoCode, setDemoCode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const requested = useRef(false);

  useEffect(() => {
    if (!userNeedsOtp(user) || requested.current) return;
    requested.current = true;
    void requestOtp()
      .then((res) => {
        setInfo(res.detail || 'A verification code was sent to your email.');
        if (res.demo_code) {
          setDemoCode(res.demo_code);
          setCode(res.demo_code);
        }
      })
      .catch((err) => setError(errorMessage(err)));
  }, [user, requestOtp]);

  if (!user) return <Navigate to="/login" replace />;
  if (!userNeedsOtp(user)) return <Navigate to={from} replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await verifyOtp(code.trim());
      navigate(from === '/login' ? '/platform' : from, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <PageHeader
        eyebrow="Security"
        title="Verify your email"
        subtitle="Demo verification — no email is sent. Use the code shown below."
      />
      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <label className="block space-y-1.5">
          <span className="text-xs uppercase tracking-wide text-muted">Verification code</span>
          <Input
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            required
          />
        </label>
        {demoCode && (
          <p className="rounded-xl border border-amber/40 bg-amber/10 px-3 py-2 font-mono text-lg tracking-[0.4em] text-amber">
            {demoCode}
          </p>
        )}
        {info && <p className="text-sm text-mint">{info}</p>}
        {error && <p className="text-sm text-rose">{error}</p>}
        <Button type="submit" disabled={busy || code.length !== 6}>
          {busy ? 'Verifying…' : 'Verify'}
        </Button>
      </form>
    </div>
  );
}
