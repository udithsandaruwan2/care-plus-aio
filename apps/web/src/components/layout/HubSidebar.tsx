import { NavLink, useNavigate } from 'react-router-dom';
import {
  Activity,
  LayoutDashboard,
  Users,
  MessageSquare,
  Calendar,
  FileText,
  UserCircle,
  Inbox,
  ShieldAlert,
  BarChart3,
  Package,
  ClipboardList,
  LogOut,
  MapPin,
  UserPlus,
  History,
} from 'lucide-react';
import { brand } from '@care-plus/ui-tokens';
import { useAuth } from '../../auth/AuthContext';

type NavItem = { path: string; label: string; icon: typeof LayoutDashboard };

function itemsForRole(role: string | undefined): NavItem[] {
  if (role === 'caregiver') {
    return [
      { path: '/hub', label: 'Dashboard', icon: LayoutDashboard },
      { path: '/requests', label: 'Inbox', icon: Inbox },
      { path: '/presence', label: 'Presence', icon: MapPin },
      { path: '/schedule', label: 'Schedule', icon: Calendar },
      { path: '/messages', label: 'Messages', icon: MessageSquare },
      { path: '/caregiver-onboarding', label: 'Profile', icon: UserPlus },
      { path: '/account', label: 'Account', icon: UserCircle },
    ];
  }
  if (role === 'admin' || role === 'auditor') {
    return [
      { path: '/hub', label: 'Dashboard', icon: LayoutDashboard },
      { path: '/app', label: 'Serah Core', icon: Activity },
      { path: '/users', label: 'Users', icon: Users },
      { path: '/admin/catalog', label: 'Catalog', icon: Package },
      { path: '/admin/analytics', label: 'Analytics', icon: BarChart3 },
      { path: '/admin/audit', label: 'Audit Logs', icon: ShieldAlert },
      ...(role === 'admin' ? [{ path: '/leads', label: 'Leads', icon: ClipboardList }] : []),
      { path: '/account', label: 'Account', icon: UserCircle },
    ];
  }
  return [
    { path: '/hub', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/app', label: 'Serah Core', icon: Activity },
    { path: '/caregivers', label: 'Caregivers', icon: Users },
    { path: '/requests', label: 'Requests', icon: Inbox },
    { path: '/history', label: 'History', icon: History },
    { path: '/messages', label: 'Messages', icon: MessageSquare },
    { path: '/schedule', label: 'Schedule', icon: Calendar },
    { path: '/records', label: 'Records', icon: FileText },
    { path: '/account', label: 'Account', icon: UserCircle },
  ];
}

export function HubSidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const items = itemsForRole(user?.role);

  return (
    <aside className="sticky top-4 m-4 flex h-[calc(100vh-2rem)] w-[260px] shrink-0 flex-col rounded-[20px] border border-hair bg-panel shadow-[var(--cp-shadow-soft)]">
      <div className="border-b border-hair px-6 py-6">
        <NavLink to="/hub" className="flex items-center gap-3 no-underline">
          <Activity color="var(--cp-accent-cyan)" size={28} />
          <span className="bg-gradient-to-r from-cyan to-violet bg-clip-text text-lg font-bold text-transparent">
            {brand.name}
          </span>
        </NavLink>
      </div>
      <nav className="flex-1 overflow-y-auto px-4 py-6" aria-label="Hub">
        <p className="mb-3 px-3 text-xs font-semibold uppercase tracking-wider text-muted">Menu</p>
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/hub' || item.path === '/app'}
              className={({ isActive }) =>
                `mb-1 flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium no-underline transition ${
                  isActive
                    ? 'border-l-[3px] border-cyan bg-cyan/10 text-cyan'
                    : 'text-muted hover:bg-soft hover:text-mist'
                }`
              }
            >
              <Icon size={20} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>
      <div className="border-t border-hair p-4">
        <button
          type="button"
          className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-rose hover:bg-rose/10"
          onClick={() => {
            logout();
            navigate('/');
          }}
        >
          <LogOut size={20} />
          Logout
        </button>
      </div>
    </aside>
  );
}
