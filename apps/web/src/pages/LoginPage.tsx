import { FormEvent, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { ApiError } from '@care-plus/api-client';
import { useAuth } from '../auth/AuthContext';
import { readBookingIntent } from '../booking/intent';
import { BackLink } from '../components/ui/BackLink';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { PageHeader } from '../components/ui/PageHeader';
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
  const from = (location.state as { from?: string } | null)?.from ?? '/platform';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/platform" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email.trim(), password);
      const intent = readBookingIntent();
      if (intent && (from === '/platform' || from === '/app')) {
        navigate(`/caregivers/${intent.caregiverId}?book=1`, { replace: true });
      } else {
        navigate(from === '/app' ? '/platform' : from, { replace: true });
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <BackLink to="/">{t('login.backHome')}</BackLink>
      <div className="mt-4">
        <PageHeader
          eyebrow={t('login.eyebrow')}
          title={t('login.title')}
          subtitle={t('login.subtitle')}
        />
      </div>

      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <label className="block space-y-1.5">
          <span className="text-xs uppercase tracking-wide text-muted">{t('login.email')}</span>
          <Input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-xs uppercase tracking-wide text-muted">{t('login.password')}</span>
          <Input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && <p className="text-sm text-rose">{error}</p>}
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? t('action.signingIn') : t('action.signIn')}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted">
        {t('login.noAccount')}{' '}
        <Link to="/register" className="text-cyan hover:underline">
          {t('action.createAccount')}
        </Link>
      </p>
    </div>
  );
}
