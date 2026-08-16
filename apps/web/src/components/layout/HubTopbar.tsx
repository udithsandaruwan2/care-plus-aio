import { Search } from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';
import { LanguageSwitcher } from '../../i18n/LanguageSwitcher';
import { ThemeToggle } from '../../theme/ThemeToggle';

export function HubTopbar() {
  const { user } = useAuth();
  const name = user?.first_name?.trim() || user?.email?.split('@')[0] || 'Account';

  return (
    <header className="flex items-center justify-between gap-4 px-8 py-5">
      <label className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-hair bg-panel px-3 py-2 shadow-sm">
        <Search size={18} className="shrink-0 text-muted" />
        <input
          type="search"
          placeholder="Search"
          className="min-w-0 flex-1 border-0 bg-transparent text-sm text-mist outline-none placeholder:text-muted"
          aria-label="Search"
        />
      </label>
      <div className="flex items-center gap-2">
        <LanguageSwitcher />
        <ThemeToggle />
        <div className="ml-2 flex h-10 w-10 items-center justify-center rounded-full bg-cyan/15 text-sm font-semibold text-cyan">
          {name.slice(0, 1).toUpperCase()}
        </div>
      </div>
    </header>
  );
}
