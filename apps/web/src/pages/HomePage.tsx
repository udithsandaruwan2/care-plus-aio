import { lazy, Suspense, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { brand } from '@care-plus/ui-tokens';
import { AssistantState, t, type Locale } from '@care-plus/core';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { useAuth } from '../auth/AuthContext';
import { api } from '../auth/api';
import { useMicAmplitude } from '../neural-core/useMicAmplitude';

const NeuralCoreCanvas = lazy(() =>
  import('../neural-core/NeuralCoreCanvas').then((m) => ({ default: m.NeuralCoreCanvas })),
);

export function HomePage() {
  const { user, logout } = useAuth();
  const locale: Locale = 'en';
  const [health, setHealth] = useState<string>('…');
  const mic = useMicAmplitude();
  const state = mic.active ? AssistantState.LISTENING : AssistantState.IDLE;

  useEffect(() => {
    api
      .health()
      .then((h) => setHealth(`${h.status} · db ${h.db} · redis ${h.redis}`))
      .catch(() => setHealth('unreachable'));
  }, []);

  async function toggleMic() {
    if (mic.active) mic.stop();
    else await mic.start();
  }

  return (
    <AtmosphereShell>
      <main className="mx-auto flex min-h-full max-w-3xl flex-col px-6 py-10">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-display text-sm uppercase tracking-[0.2em] text-cyan">
              {brand.theme}
            </p>
            <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight text-mist sm:text-5xl">
              {brand.name}
            </h1>
          </div>
          <button
            type="button"
            onClick={logout}
            className="shrink-0 rounded-lg border border-hair px-3 py-1.5 text-sm text-muted transition hover:border-rose hover:text-rose"
          >
            Sign out
          </button>
        </div>

        {/* Neural Core — tap / click the orb or the button to speak */}
        <section className="relative mx-auto mt-6 flex w-full max-w-lg flex-col items-center">
          <button
            type="button"
            onClick={toggleMic}
            aria-pressed={mic.active}
            aria-label={mic.active ? 'Stop listening' : 'Tap to speak'}
            className="group relative h-72 w-full cursor-pointer rounded-full border-0 bg-transparent p-0 outline-none focus-visible:ring-2 focus-visible:ring-cyan"
          >
            <Suspense
              fallback={
                <div className="flex h-full items-center justify-center text-sm text-muted">
                  Loading Neural Core…
                </div>
              }
            >
              <NeuralCoreCanvas
                amplitude={mic.amplitude}
                state={state}
                className="pointer-events-none h-full w-full"
              />
            </Suspense>
          </button>

          <p className="mt-2 font-display text-sm tracking-wide text-cyan">
            {state} · {mic.active ? t(locale, 'assistant.listening') : t(locale, 'assistant.idle')}
          </p>
          {mic.error && <p className="mt-1 text-sm text-rose">{mic.error}</p>}
          <p className="mt-1 text-xs text-muted">
            Level {(mic.amplitude * 100).toFixed(0)}% · idle uses on-demand render
          </p>

          <button
            type="button"
            onClick={toggleMic}
            className={`mt-4 rounded-full px-6 py-2.5 text-sm font-medium transition ${
              mic.active
                ? 'bg-rose/20 text-rose ring-1 ring-rose/50'
                : 'bg-cyan/90 text-void hover:bg-cyan'
            }`}
          >
            {mic.active ? 'Stop' : 'Tap to speak'}
          </button>
        </section>

        <div className="mt-8 rounded-2xl border border-hair bg-panel p-5 backdrop-blur-md">
          <div className="flex items-center justify-between gap-4">
            <span className="text-sm text-muted">Signed in as</span>
            <span className="font-mono text-sm text-mint">
              {user?.email} · {user?.role}
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between gap-4">
            <span className="text-sm text-muted">API health</span>
            <span className="font-mono text-sm text-mint">{health}</span>
          </div>
          <p className="mt-4 text-sm text-muted">
            Neural Core (Step 11). FSM + Goal Ring in{' '}
            <Link to="/" className="text-cyan">
              Step 12
            </Link>
            ; live transcript in Step 13.
          </p>
        </div>
      </main>
    </AtmosphereShell>
  );
}
