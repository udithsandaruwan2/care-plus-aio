import { Outlet, useLocation } from 'react-router-dom';
import { SkipLink } from '../../a11y/SkipLink';
import { SerahEngineProvider } from '../../assistant/SerahEngine';
import { HubSidebar } from './HubSidebar';
import { HubTopbar } from './HubTopbar';
import { AIAssistantDock } from './AIAssistantDock';

export function AppShell() {
  const { pathname } = useLocation();
  const serahCore = pathname === '/app';

  return (
    <SerahEngineProvider>
      <div className="flex min-h-screen bg-void">
        <SkipLink />
        <HubSidebar />
        <div className="flex min-h-screen min-w-0 flex-1 flex-col overflow-hidden">
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
