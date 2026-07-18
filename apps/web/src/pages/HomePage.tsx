import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { brand } from '@care-plus/ui-tokens';
import { AssistantState, t, type Locale } from '@care-plus/core';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { useAuth } from '../auth/AuthContext';
import { api } from '../auth/api';

export function HomePage() {
  const { user, logout } = useAuth();
  const locale: Locale = 'en';
  const [health, setHealth] = useState<string>('…');

  useEffect(() => {
    api
      .health()
      .then((h) => setHealth(`${h.status} · db ${h.db} · redis ${h.redis}`))
      .catch(() => setHealth('unreachable'));
  }, []);

  return (
    <AtmosphereShell>
      <main className="mx-auto flex min-h-full max-w-3xl flex-col justify-center px-6 py-16">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-display text-sm uppercase tracking-[0.2em] text-cyan">
              {brand.theme}
            </p>
            <h1 className="mt-3 font-display text-5xl font-semibold tracking-tight text-mist sm:text-6xl">
              {brand.name}
            </h1>
            <p className="mt-4 max-w-md text-lg text-muted">{t(locale, 'app.tagline')}</p>
          </div>
          <button
            type="button"
            onClick={logout}
            className="shrink-0 rounded-lg border border-hair px-3 py-1.5 text-sm text-muted transition hover:border-rose hover:text-rose"
          >
            Sign out
          </button>
        </div>

        <div className="mt-10 rounded-2xl border border-hair bg-panel p-6 backdrop-blur-md">
          <div className="flex items-center justify-between gap-4">
            <span className="text-sm text-muted">Signed in as</span>
            <span className="font-mono text-sm text-mint">
              {user?.email} · {user?.role}
            </span>
          </div>
          <div className="mt-4 flex items-center justify-between gap-4">
            <span className="text-sm text-muted">API health</span>
            <span className="font-mono text-sm text-mint">{health}</span>
          </div>
          <div className="mt-4 flex items-center justify-between gap-4">
            <span className="text-sm text-muted">Assistant FSM</span>
            <span className="rounded-full border border-hair px-3 py-1 text-xs text-cyan">
              {AssistantState.IDLE} · {t(locale, 'assistant.idle')}
            </span>
          </div>
          <p className="mt-6 text-sm text-muted">
            Authed home via JWT. Neural Core lands in{' '}
            <Link to="/" className="text-cyan">
              Step 11
            </Link>
            .
          </p>
        </div>
      </main>
    </AtmosphereShell>
  );
}
