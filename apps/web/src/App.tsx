import { useEffect, useState } from 'react';
import { brand, colors } from '@care-plus/ui-tokens';
import { AssistantState, t, type Locale } from '@care-plus/core';
import { createApiClient } from '@care-plus/api-client';

const api = createApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
});

export function App() {
  const locale: Locale = 'en';
  const [health, setHealth] = useState<string>('…');

  useEffect(() => {
    api
      .health()
      .then((h) => setHealth(`${h.status} · db ${h.db} · redis ${h.redis}`))
      .catch(() => setHealth('unreachable (start docker stack)'));
  }, []);

  return (
    <div className="relative min-h-full overflow-hidden">
      {/* Atmosphere — soft nebula wash (not flat void) */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background: `
            radial-gradient(ellipse 80% 50% at 20% 10%, ${colors.accentViolet}22, transparent 55%),
            radial-gradient(ellipse 60% 40% at 85% 20%, ${colors.accentCyan}18, transparent 50%),
            radial-gradient(ellipse 50% 60% at 50% 100%, ${colors.accentMint}10, transparent 45%),
            ${colors.bgVoid}
          `,
        }}
      />

      <main className="relative z-10 mx-auto flex min-h-full max-w-3xl flex-col justify-center px-6 py-16">
        <p className="font-display text-sm uppercase tracking-[0.2em] text-cyan">{brand.theme}</p>
        <h1 className="mt-3 font-display text-5xl font-semibold tracking-tight text-mist sm:text-6xl">
          {brand.name}
        </h1>
        <p className="mt-4 max-w-md text-lg text-muted">{t(locale, 'app.tagline')}</p>

        <div
          className="mt-10 rounded-2xl border border-hair bg-panel p-6 backdrop-blur-md"        >
          <div className="flex items-center justify-between gap-4">
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
            Tokens from <code className="text-cyan">@care-plus/ui-tokens</code> · core + api-client
            wired. Neural Core lands in Step 11.
          </p>
        </div>
      </main>
    </div>
  );
}
