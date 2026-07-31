import { useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { brand } from '@care-plus/ui-tokens';
import { useAuth } from '../../auth/AuthContext';
import { ThemeToggle } from '../../theme/ThemeToggle';

const PRIMARY_NAV = [
  { to: '/platform', label: 'Home', end: true },
  { to: '/app', label: 'Assistant', end: true },
  { to: '/requests', label: 'Requests' },
  { to: '/schedule', label: 'Schedule' },
  { to: '/messages', label: 'Messages' },
  { to: '/records', label: 'Records' },
  { to: '/account', label: 'Account' },
];

function navClass(isActive: boolean) {
  return `rounded-full px-3 py-1.5 text-xs transition ${
    isActive
      ? 'border border-cyan/50 bg-cyan/10 text-cyan'
      : 'border border-transparent text-muted hover:border-hair hover:text-mist'
  }`;
}

export function AppTopBar({ showBack = true }: { showBack?: boolean }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);

  const isHome = location.pathname === '/platform';
  const showBackButton = showBack && !isHome;

  function onBack() {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate('/platform');
    }
  }

  const profilePath = user?.role === 'caregiver' ? '/caregiver-onboarding' : '/onboarding';

  return (
    <header className="sticky top-0 z-30 border-b border-hair/80 bg-panel/95 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-2">
          {showBackButton && (
            <button
              type="button"
              onClick={onBack}
              className="rounded-full border border-hair px-3 py-1 text-xs text-muted transition hover:border-cyan hover:text-cyan"
            >
              Back
            </button>
          )}
          <Link to="/platform" className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-cyan" />
            <span className="font-display text-base text-mist">{brand.name}</span>
          </Link>
        </div>

        <nav className="hidden items-center gap-1 md:flex">
          {PRIMARY_NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => navClass(isActive)}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <div className="relative">
            <button
              type="button"
              onClick={() => setAccountOpen((v) => !v)}
              className="rounded-full border border-hair px-3 py-1.5 text-xs text-muted hover:border-cyan hover:text-cyan"
            >
              Menu
            </button>
            {accountOpen && (
              <div className="absolute right-0 mt-2 w-52 rounded-2xl border border-hair bg-panel p-2 shadow-[var(--cp-shadow-soft)]">
                <Link
                  to={profilePath}
                  className="block rounded-xl px-3 py-2 text-xs text-muted hover:bg-soft hover:text-mist"
                  onClick={() => setAccountOpen(false)}
                >
                  Edit profile
                </Link>
                <Link
                  to="/settings/notifications"
                  className="block rounded-xl px-3 py-2 text-xs text-muted hover:bg-soft hover:text-mist"
                  onClick={() => setAccountOpen(false)}
                >
                  Notifications
                </Link>
                {(user?.role === 'patient' || user?.role === 'caregiver') && (
                  <Link
                    to="/schedule"
                    className="block rounded-xl px-3 py-2 text-xs text-muted hover:bg-soft hover:text-mist"
                    onClick={() => setAccountOpen(false)}
                  >
                    Schedule
                  </Link>
                )}
                {user?.role === 'caregiver' && (
                  <Link
                    to="/presence"
                    className="block rounded-xl px-3 py-2 text-xs text-muted hover:bg-soft hover:text-mist"
                    onClick={() => setAccountOpen(false)}
                  >
                    Soft presence
                  </Link>
                )}
                {(user?.role === 'admin' || user?.role === 'auditor') && (
                  <Link
                    to="/users"
                    className="block rounded-xl px-3 py-2 text-xs text-muted hover:bg-soft hover:text-mist"
                    onClick={() => setAccountOpen(false)}
                  >
                    Users
                  </Link>
                )}
                {(user?.role === 'admin' || user?.role === 'auditor') && (
                  <Link
                    to="/admin/analytics"
                    className="block rounded-xl px-3 py-2 text-xs text-muted hover:bg-soft hover:text-mist"
                    onClick={() => setAccountOpen(false)}
                  >
                    Analytics
                  </Link>
                )}
                {(user?.role === 'admin' || user?.role === 'auditor') && (
                  <Link
                    to="/admin/audit"
                    className="block rounded-xl px-3 py-2 text-xs text-muted hover:bg-soft hover:text-mist"
                    onClick={() => setAccountOpen(false)}
                  >
                    Audit log
                  </Link>
                )}
                {(user?.role === 'admin' || user?.role === 'auditor') && (
                  <Link
                    to="/admin/catalog"
                    className="block rounded-xl px-3 py-2 text-xs text-muted hover:bg-soft hover:text-mist"
                    onClick={() => setAccountOpen(false)}
                  >
                    Vocab & catalog
                  </Link>
                )}
                {user?.role === 'admin' && (
                  <Link
                    to="/leads"
                    className="block rounded-xl px-3 py-2 text-xs text-muted hover:bg-soft hover:text-mist"
                    onClick={() => setAccountOpen(false)}
                  >
                    Leads
                  </Link>
                )}
                <Link
                  to="/caregivers"
                  className="block rounded-xl px-3 py-2 text-xs text-muted hover:bg-soft hover:text-mist"
                  onClick={() => setAccountOpen(false)}
                >
                  Browse caregivers
                </Link>
                <Link
                  to="/"
                  className="block rounded-xl px-3 py-2 text-xs text-muted hover:bg-soft hover:text-mist"
                  onClick={() => setAccountOpen(false)}
                >
                  Public site
                </Link>
                <button
                  type="button"
                  className="mt-1 w-full rounded-xl px-3 py-2 text-left text-xs text-rose hover:bg-rose/10"
                  onClick={() => {
                    setAccountOpen(false);
                    logout();
                  }}
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
          <button
            type="button"
            className="rounded-full border border-hair px-3 py-1.5 text-xs text-muted md:hidden"
            onClick={() => setMenuOpen((v) => !v)}
            aria-expanded={menuOpen}
          >
            Nav
          </button>
        </div>
      </div>

      {menuOpen && (
        <nav className="border-t border-hair px-4 py-3 md:hidden">
          <div className="flex flex-wrap gap-2">
            {PRIMARY_NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) => navClass(isActive)}
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        </nav>
      )}
    </header>
  );
}
