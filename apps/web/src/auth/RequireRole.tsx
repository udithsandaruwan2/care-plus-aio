import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from './AuthContext';

type Role = 'patient' | 'caregiver' | 'admin' | 'auditor';

/** Route gate by role — redirects to hub when the signed-in user is not allowed. */
export function RequireRole({ roles }: { roles: Role[] }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-full items-center justify-center text-muted">
        Restoring session…
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!roles.includes(user.role as Role)) {
    return <Navigate to="/hub" replace />;
  }

  return <Outlet />;
}
