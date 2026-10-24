import { NavLink } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { mobileTabsForRole } from './hubNav';

export function HubBottomNav() {
  const { user } = useAuth();
  const items = mobileTabsForRole(user?.role);

  return (
    <nav
      className="hub-bottom-nav lg:hidden"
      aria-label="App"
    >
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/hub' || item.path === '/app'}
            className={({ isActive }) =>
              `hub-bottom-nav-item ${isActive ? 'is-active' : ''}`
            }
          >
            <Icon size={22} strokeWidth={2.1} />
            <span>{item.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}
