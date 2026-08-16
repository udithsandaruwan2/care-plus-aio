import { FormEvent, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { ApiError, userNeedsOtp } from '@care-plus/api-client';
import { useAuth } from '../auth/AuthContext';
import { readBookingIntent } from '../booking/intent';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { useLocale } from '../i18n/LocaleProvider';

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
  const { t } = useLocale();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? '/hub';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
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
      const me = await login(email.trim(), password);
      if (userNeedsOtp(me)) {
        navigate('/otp', { replace: true, state: { from } });
        return;
      }
      const intent = readBookingIntent();
      if (intent && (from === '/hub' || from === '/app')) {
        navigate(`/caregivers/${intent.caregiverId}?book=1`, { replace: true });
      } else {
        navigate(from === '/app' ? '/hub' : from, { replace: true });
      }
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
          <h1 className="mt-3 font-display text-2xl font-bold text-mist">{t('login.title')}</h1>
          <p className="mt-2 text-sm text-muted">{t('login.subtitle')}</p>
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <label className="block space-y-1.5">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted">
              {t('login.email')}
            </span>
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
              {t('login.password')}
            </span>
            <Input
              type="password"
              required
              autoComplete="current-password"
              placeholder="••••••••"
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
            {busy ? t('action.signingIn') : t('action.signIn')}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted">
          {t('login.noAccount')}{' '}
          <Link to="/register" className="font-semibold text-cyan hover:underline">
            {t('action.createAccount')}
          </Link>
        </p>
        <p className="mt-3 text-center text-xs text-muted">
          <Link to="/" className="hover:text-cyan">
            {t('login.backHome')}
          </Link>
        </p>
      </Card>
    </div>
  );
}
