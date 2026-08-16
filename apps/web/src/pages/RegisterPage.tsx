import { FormEvent, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { ApiError, userNeedsOtp } from '@care-plus/api-client';
import { useAuth } from '../auth/AuthContext';
import { readBookingIntent } from '../booking/intent';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const body = err.body as Record<string, unknown> | null;
    if (body && typeof body === 'object') {
      for (const key of ['email', 'password', 'detail', 'non_field_errors']) {
        const val = body[key];
        if (typeof val === 'string') return val;
        if (Array.isArray(val) && typeof val[0] === 'string') return val[0];
      }
    }
    return `Request failed (${err.status}).`;
  }
  return 'Something went wrong. Try again.';
}

export function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'patient' | 'caregiver'>('patient');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) {
    if (userNeedsOtp(user)) return <Navigate to="/otp" replace />;
    return <Navigate to="/hub" replace />;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const me = await register(email.trim(), password, role);
      if (userNeedsOtp(me)) {
        navigate('/otp', { replace: true });
        return;
      }
      const intent = readBookingIntent();
      if (intent && role === 'patient') {
        navigate(`/caregivers/${intent.caregiverId}?book=1`, { replace: true });
        return;
      }
      navigate(role === 'patient' ? '/onboarding' : '/caregiver-onboarding', { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-12rem)] items-center justify-center px-6 py-12">
      <Card className="w-full max-w-md p-8">
        <div className="mb-6 text-center">
          <Activity className="mx-auto text-cyan" size={32} />
          <h1 className="mt-3 font-display text-2xl font-bold text-mist">Create an Account</h1>
          <p className="mt-2 text-sm text-muted">Join Care Plus as a patient or caregiver.</p>
        </div>

        <div className="mb-5 flex gap-2">
          {(['patient', 'caregiver'] as const).map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setRole(r)}
              className={`flex-1 rounded-xl border px-3 py-2.5 text-sm font-semibold capitalize transition ${
                role === r
                  ? 'border-cyan bg-cyan/10 text-cyan'
                  : 'border-hair text-muted hover:border-cyan/40'
              }`}
            >
              I&apos;m a {r}
            </button>
          ))}
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <label className="block space-y-1.5">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted">Email</span>
            <Input
              type="email"
              required
              autoComplete="email"
              placeholder="name@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted">
              Password
            </span>
            <Input
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              placeholder="Min. 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && (
            <p className="text-sm text-rose" role="alert">
              {error}
            </p>
          )}
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? 'Creating…' : 'Create account'}
          </Button>
        </form>

        <p className="mt-4 text-center text-xs text-muted">
          By creating an account you agree to our{' '}
          <Link to="/privacy" className="text-cyan hover:underline">
            privacy notice (PDPA)
          </Link>
          .
        </p>
        <p className="mt-6 text-center text-sm text-muted">
          Already registered?{' '}
          <Link to="/login" className="font-semibold text-cyan hover:underline">
            Sign in
          </Link>
        </p>
      </Card>
    </div>
  );
}
