import { FormEvent, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { ApiError } from '@care-plus/api-client';
import { useAuth } from '../auth/AuthContext';
import { readBookingIntent } from '../booking/intent';
import { BackLink } from '../components/ui/BackLink';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { PageHeader } from '../components/ui/PageHeader';

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

  if (user) return <Navigate to="/platform" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await register(email.trim(), password, role);
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
    <div className="mx-auto max-w-md">
      <BackLink to="/">Home</BackLink>
      <div className="mt-4">
        <PageHeader
          eyebrow="Care Plus"
          title="Create account"
          subtitle="Join as a patient or caregiver to book home care in Sri Lanka."
        />
      </div>

      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <label className="block space-y-1.5">
          <span className="text-xs uppercase tracking-wide text-muted">Email</span>
          <Input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-xs uppercase tracking-wide text-muted">Password</span>
          <Input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <fieldset className="space-y-2">
          <legend className="text-xs uppercase tracking-wide text-muted">I am a</legend>
          <div className="flex gap-3">
            {(['patient', 'caregiver'] as const).map((r) => (
              <label
                key={r}
                className={`flex-1 cursor-pointer rounded-2xl border px-3 py-2.5 text-center text-sm capitalize ${
                  role === r
                    ? 'border-cyan text-cyan'
                    : 'border-hair text-muted hover:border-cyan/40'
                }`}
              >
                <input
                  type="radio"
                  name="role"
                  value={r}
                  checked={role === r}
                  onChange={() => setRole(r)}
                  className="sr-only"
                />
                {r}
              </label>
            ))}
          </div>
        </fieldset>
        {error && (
          <p className="text-sm text-rose" role="alert">
            {error}
          </p>
        )}
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? 'Creating…' : 'Create account'}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted">
        Already registered?{' '}
        <Link to="/login" className="text-cyan hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
