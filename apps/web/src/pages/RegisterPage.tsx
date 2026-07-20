import { FormEvent, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { brand } from '@care-plus/ui-tokens';
import { ApiError } from '@care-plus/api-client';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { useAuth } from '../auth/AuthContext';

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

  if (user) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await register(email.trim(), password, role);
      navigate(role === 'patient' ? '/onboarding' : '/', { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AtmosphereShell>
      <main className="mx-auto flex min-h-full max-w-md flex-col justify-center px-6 py-16">
        <p className="font-display text-sm uppercase tracking-[0.2em] text-cyan">{brand.theme}</p>
        <h1 className="mt-2 font-display text-3xl font-semibold text-mist">Create account</h1>
        <p className="mt-2 text-sm text-muted">Patients and caregivers can self-register.</p>

        <form
          onSubmit={onSubmit}
          className="mt-8 space-y-4 rounded-2xl border border-hair bg-panel p-6 backdrop-blur-md"
        >
          <label className="block space-y-1.5">
            <span className="text-xs uppercase tracking-wide text-muted">Email</span>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-hair bg-void/60 px-3 py-2 text-mist outline-none ring-cyan focus:ring-1"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs uppercase tracking-wide text-muted">Password</span>
            <input
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-hair bg-void/60 px-3 py-2 text-mist outline-none ring-cyan focus:ring-1"
            />
          </label>
          <fieldset className="space-y-2">
            <legend className="text-xs uppercase tracking-wide text-muted">I am a</legend>
            <div className="flex gap-3">
              {(['patient', 'caregiver'] as const).map((r) => (
                <label
                  key={r}
                  className={`flex-1 cursor-pointer rounded-lg border px-3 py-2 text-center text-sm capitalize ${
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
          {error && <p className="text-sm text-rose">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-cyan/90 px-4 py-2.5 font-medium text-void transition hover:bg-cyan disabled:opacity-60"
          >
            {busy ? 'Creating…' : 'Create account'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-muted">
          Already registered?{' '}
          <Link to="/login" className="text-cyan hover:underline">
            Sign in
          </Link>
        </p>
      </main>
    </AtmosphereShell>
  );
}
