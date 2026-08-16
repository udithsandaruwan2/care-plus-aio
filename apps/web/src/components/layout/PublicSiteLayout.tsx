import { Outlet } from 'react-router-dom';
import { SkipLink } from '../../a11y/SkipLink';
import { PublicFooter } from './PublicFooter';
import { PublicHeader } from './PublicHeader';

export function PublicSiteLayout() {
  return (
    <div className="flex min-h-full flex-col bg-panel">
      <SkipLink />
      <PublicHeader />
      <main id="main-content" tabIndex={-1} className="flex-1 outline-none">
        <Outlet />
      </main>
      <PublicFooter />
    </div>
  );
}
