import { useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { SkipLink } from '../../a11y/SkipLink';
import { bindEdgeRankingLifecycle } from '../../assistant/useMatch';
import { bindOutboxLifecycle } from '../../lib/outbox/flush';
import { OfflineBanner } from '../OfflineBanner';
import { OutboxBanner } from '../OutboxBanner';
import { PublicFooter } from './PublicFooter';
import { PublicHeader } from './PublicHeader';

export function PublicSiteLayout() {
  useEffect(() => {
    const unbindOutbox = bindOutboxLifecycle();
    const unbindEdge = bindEdgeRankingLifecycle();
    return () => {
      unbindOutbox();
      unbindEdge();
    };
  }, []);

  return (
    <div className="flex min-h-full flex-col bg-panel">
      <SkipLink />
      <OfflineBanner />
      <OutboxBanner />
      <PublicHeader />
      <main id="main-content" tabIndex={-1} className="flex-1 outline-none">
        <Outlet />
      </main>
      <PublicFooter />
    </div>
  );
}
