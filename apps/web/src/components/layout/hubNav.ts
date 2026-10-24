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
  MapPin,
  UserPlus,
  History,
  type LucideIcon,
} from 'lucide-react';

export type HubNavItem = { path: string; label: string; icon: LucideIcon };

export function itemsForRole(role: string | undefined): HubNavItem[] {
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
      { path: '/app', label: 'Serah', icon: Activity },
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
    { path: '/app', label: 'Serah', icon: Activity },
    { path: '/caregivers', label: 'Caregivers', icon: Users },
    { path: '/requests', label: 'Requests', icon: Inbox },
    { path: '/orders', label: 'Orders', icon: Package },
    { path: '/history', label: 'History', icon: History },
    { path: '/messages', label: 'Messages', icon: MessageSquare },
    { path: '/schedule', label: 'Schedule', icon: Calendar },
    { path: '/records', label: 'Records', icon: FileText },
    { path: '/account', label: 'Account', icon: UserCircle },
  ];
}

/** Five thumb-reach tabs for a 412px Pixel 7 Pro width. */
export function mobileTabsForRole(role: string | undefined): HubNavItem[] {
  if (role === 'caregiver') {
    return [
      { path: '/hub', label: 'Home', icon: LayoutDashboard },
      { path: '/requests', label: 'Inbox', icon: Inbox },
      { path: '/schedule', label: 'Schedule', icon: Calendar },
      { path: '/messages', label: 'Chats', icon: MessageSquare },
      { path: '/account', label: 'You', icon: UserCircle },
    ];
  }
  if (role === 'admin' || role === 'auditor') {
    return [
      { path: '/hub', label: 'Home', icon: LayoutDashboard },
      { path: '/app', label: 'Serah', icon: Activity },
      { path: '/users', label: 'Users', icon: Users },
      { path: '/admin/analytics', label: 'Stats', icon: BarChart3 },
      { path: '/account', label: 'You', icon: UserCircle },
    ];
  }
  return [
    { path: '/hub', label: 'Home', icon: LayoutDashboard },
    { path: '/app', label: 'Serah', icon: Activity },
    { path: '/requests', label: 'Requests', icon: Inbox },
    { path: '/messages', label: 'Chats', icon: MessageSquare },
    { path: '/account', label: 'You', icon: UserCircle },
  ];
}
