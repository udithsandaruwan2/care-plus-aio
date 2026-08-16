import { useCallback, useRef, useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { brand } from '@care-plus/ui-tokens';
import { useFocusTrap } from '../../a11y/useFocusTrap';
import { useAuth } from '../../auth/AuthContext';
import { LanguageSwitcher } from '../../i18n/LanguageSwitcher';
import { useLocale } from '../../i18n/LocaleProvider';
import { Button } from '../ui/Button';

function linkClass(isActive: boolean) {
  return `text-sm font-medium no-underline transition ${
    isActive ? 'text-cyan' : 'text-muted hover:text-cyan'
  }`;
}

export function PublicHeader() {
  const { user } = useAuth();
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const mobileNavRef = useRef<HTMLElement>(null);
  const closeMobile = useCallback(() => setOpen(false), []);
  useFocusTrap(open, mobileNavRef, closeMobile);

  const nav = (
    <>
      <NavLink
        to="/caregivers"
        className={({ isActive }) => linkClass(isActive)}
        onClick={() => setOpen(false)}
      >
        Find Caregivers
      </NavLink>
      <NavLink
        to="/catalog"
        className={({ isActive }) => linkClass(isActive)}
        onClick={() => setOpen(false)}
      >
        Packages
      </NavLink>
      <NavLink
        to="/contact"
        className={({ isActive }) => linkClass(isActive)}
        onClick={() => setOpen(false)}
      >
        Contact
      </NavLink>
      {user && (
        <NavLink
          to="/hub"
          className={({ isActive }) => linkClass(isActive)}
          onClick={() => setOpen(false)}
        >
          {t('nav.app')}
        </NavLink>
      )}
    </>
  );

  return (
    <header className="sticky top-0 z-20 border-b border-hair bg-panel">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-6 py-4">
        <Link to="/" className="flex items-center gap-3 no-underline">
          <Activity color="var(--cp-accent-cyan)" size={28} />
          <span className="bg-gradient-to-r from-cyan to-violet bg-clip-text text-xl font-bold text-transparent">
            {brand.name}
          </span>
        </Link>
        <nav className="hidden items-center gap-8 md:flex" aria-label="Primary">
          {nav}
        </nav>
        <div className="flex items-center gap-2">
          <LanguageSwitcher />
          {user ? (
            <Link to="/hub">
              <Button className="min-h-10 px-4 py-2">{t('action.openApp')}</Button>
            </Link>
          ) : (
            <>
              <Link to="/login" className="hidden sm:block">
                <Button tone="ghost" className="min-h-10 px-4 py-2">
                  Log In
                </Button>
              </Link>
              <Link to="/register">
                <Button className="min-h-10 px-4 py-2">Register</Button>
              </Link>
            </>
          )}
          <button
            type="button"
            className="rounded-xl border border-hair px-3 py-1.5 text-xs text-muted md:hidden"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls="public-mobile-nav"
          >
            {t('action.menu')}
          </button>
        </div>
      </div>
      {open && (
        <nav
          id="public-mobile-nav"
          ref={mobileNavRef}
          className="flex flex-col gap-2 border-t border-hair px-6 py-3 md:hidden"
          aria-label="Mobile primary"
        >
          {nav}
        </nav>
      )}
    </header>
  );
}
