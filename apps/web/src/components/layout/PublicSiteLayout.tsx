import { Outlet, useLocation } from 'react-router-dom';
import { AtmosphereShell } from '../AtmosphereShell';
import { SkipLink } from '../../a11y/SkipLink';
import { AIAssistantDock } from './AIAssistantDock';
import { PublicFooter } from './PublicFooter';
import { PublicHeader } from './PublicHeader';

const HIDE_DOCK = new Set(['/login', '/register']);

export function PublicSiteLayout() {
  const location = useLocation();
  const showDock = !HIDE_DOCK.has(location.pathname);

  return (
    <AtmosphereShell>
      <SkipLink />
      <div className="mx-auto flex min-h-full w-full max-w-6xl flex-col px-5 sm:px-8">
        <PublicHeader />
        <main id="main-content" tabIndex={-1} className="flex-1 pb-10 pt-6 outline-none sm:pt-8">
          <Outlet />
        </main>
        <PublicFooter />
      </div>
      {showDock && <AIAssistantDock />}
    </AtmosphereShell>
  );
}
