import { useEffect } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { SkipLink } from '../../a11y/SkipLink';
import { SerahEngineProvider } from '../../assistant/SerahEngine';
import { bindAppNavigate } from '../../assistant/appNavigate';
import { api } from '../../auth/api';
import { useAuth } from '../../auth/AuthContext';
import { useConnectionStore } from '../../auth/connectionStore';
import { bindEdgeRankingLifecycle } from '../../assistant/useMatch';
import { bindOutboxLifecycle } from '../../lib/outbox/flush';
import { OutboxBanner } from '../OutboxBanner';
import { AIAssistantDock } from './AIAssistantDock';
import { HubBottomNav } from './HubBottomNav';
import { HubSidebar } from './HubSidebar';
import { HubTopbar } from './HubTopbar';

function ConnectionBanner() {
  const kind = useConnectionStore((s) => s.kind);
  const sessionStale = useAuth().sessionStale;

  useEffect(() => {
    if (kind !== 'degraded' && !sessionStale) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void api
        .health()
        .then(() => {
          if (!cancelled) useConnectionStore.getState().noteRequestOutcome('ok');
        })
        .catch(() => undefined);
    }, 600);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [kind, sessionStale]);

  if (kind === 'online' && !sessionStale) return null;

  const offline = kind === 'offline';
  const message = offline
    ? 'You are offline. Showing your last saved session — some actions will wait until you reconnect.'
    : sessionStale
      ? 'Connection is unstable. You are still signed in with your last known profile.'
      : 'Connection issues detected. Retrying when possible…';

  return (
    <div
      role="status"
      className={
        offline
          ? 'border-b border-amber/40 bg-amber/10 px-4 py-2 text-center text-xs text-mist'
          : 'border-b border-rose/30 bg-rose/5 px-4 py-2 text-center text-xs text-mist'
      }
    >
      {message}{' '}
      {offline ? (
        <a href="/offline" className="underline underline-offset-2">
          Offline help
        </a>
      ) : null}
    </div>
  );
}

export function AppShell() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const serahCore = pathname === '/app';

  useEffect(() => {
    bindAppNavigate((to, opts) => {
      navigate(to, { replace: opts?.replace });
    });
    return () => bindAppNavigate(null);
  }, [navigate]);

  useEffect(() => {
    const unbindOutbox = bindOutboxLifecycle();
    const unbindEdge = bindEdgeRankingLifecycle();
    return () => {
      unbindOutbox();
      unbindEdge();
    };
  }, []);

  return (
    <SerahEngineProvider>
      <div className={`flex min-h-dvh bg-void ${serahCore ? 'is-serah-core' : ''}`}>
        <SkipLink />
        <HubSidebar />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <ConnectionBanner />
          <OutboxBanner />
          {serahCore ? (
            <div className="hidden lg:block">
              <HubTopbar />
            </div>
          ) : (
            <>
              <HubTopbar compact />
              <HubTopbar />
            </>
          )}
          <main
            id="main-content"
            tabIndex={-1}
            className={
              serahCore
                ? 'flex min-h-0 flex-1 flex-col overflow-hidden px-0 pb-0 outline-none lg:px-4 lg:pb-4'
                : 'flex-1 overflow-y-auto px-4 pb-[calc(5.75rem+env(safe-area-inset-bottom))] outline-none lg:px-8 lg:pb-8'
            }
          >
            <Outlet />
          </main>
          {serahCore ? null : <HubBottomNav />}
        </div>
        <AIAssistantDock />
      </div>
    </SerahEngineProvider>
  );
}
