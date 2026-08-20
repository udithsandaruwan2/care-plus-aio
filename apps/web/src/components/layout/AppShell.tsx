import { Outlet, useLocation } from 'react-router-dom';
import { SkipLink } from '../../a11y/SkipLink';
import { SerahEngineProvider } from '../../assistant/SerahEngine';
import { useAuth } from '../../auth/AuthContext';
import { useConnectionStore } from '../../auth/connectionStore';
import { HubSidebar } from './HubSidebar';
import { HubTopbar } from './HubTopbar';
import { AIAssistantDock } from './AIAssistantDock';

function ConnectionBanner() {
  const kind = useConnectionStore((s) => s.kind);
  const sessionStale = useAuth().sessionStale;

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
      {message}
    </div>
  );
}

export function AppShell() {
  const { pathname } = useLocation();
  const serahCore = pathname === '/app';

  return (
    <SerahEngineProvider>
      <div className="flex min-h-screen bg-void">
        <SkipLink />
        <HubSidebar />
        <div className="flex min-h-screen min-w-0 flex-1 flex-col overflow-hidden">
          <ConnectionBanner />
          <HubTopbar />
          <main
            id="main-content"
            tabIndex={-1}
            className={
              serahCore
                ? 'flex min-h-0 flex-1 flex-col overflow-hidden px-4 pb-4 outline-none'
                : 'flex-1 overflow-y-auto px-8 pb-8 outline-none'
            }
          >
            <Outlet />
          </main>
        </div>
        <AIAssistantDock />
      </div>
    </SerahEngineProvider>
  );
}
