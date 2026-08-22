import { useAuth } from '../../auth/AuthContext';
import { AppShell } from './AppShell';
import { PublicSiteLayout } from './PublicSiteLayout';

/**
 * Layout for pages that are public but also reachable from the hub sidebar
 * (caregiver directory, catalog). Signed-in users keep the app shell and its
 * left navigation; visitors get the marketing header/footer.
 */
export function SessionAwareLayout() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-void text-muted">
        Restoring session…
      </div>
    );
  }

  return user ? <AppShell /> : <PublicSiteLayout />;
}
