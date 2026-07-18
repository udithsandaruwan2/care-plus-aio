import { FormEvent, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { brand } from '@care-plus/ui-tokens';
import { ApiError } from '@care-plus/api-client';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { useAuth } from '../auth/AuthContext';

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const body = err.body as { detail?: string; email?: string[] } | null;
    if (typeof body?.detail === 'string') return body.detail;
    if (body?.email?.[0]) return body.email[0];
    if (err.status === 401) return 'Invalid email or password.';
    return `Request failed (${err.status}).`;
  }
  return 'Something went wrong. Try again.';
}

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? '/';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email.trim(), password);
      navigate(from, { replace: true });
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
        <h1 className="mt-2 font-display text-3xl font-semibold text-mist">Sign in</h1>
        <p className="mt-2 text-sm text-muted">Use your Care Plus account to continue.</p>

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
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-hair bg-void/60 px-3 py-2 text-mist outline-none ring-cyan focus:ring-1"
            />
          </label>
          {error && <p className="text-sm text-rose">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-cyan/90 px-4 py-2.5 font-medium text-void transition hover:bg-cyan disabled:opacity-60"
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-muted">
          No account?{' '}
          <Link to="/register" className="text-cyan hover:underline">
            Create one
          </Link>
        </p>
      </main>
    </AtmosphereShell>
  );
}
