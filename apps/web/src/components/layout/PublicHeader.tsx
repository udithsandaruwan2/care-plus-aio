import { useCallback, useRef, useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { brand } from '@care-plus/ui-tokens';
import { useFocusTrap } from '../../a11y/useFocusTrap';
import { useAuth } from '../../auth/AuthContext';
import { LanguageSwitcher } from '../../i18n/LanguageSwitcher';
import { useLocale } from '../../i18n/LocaleProvider';
import { ThemeToggle } from '../../theme/ThemeToggle';
import { Button } from '../ui/Button';

function linkClass(isActive: boolean) {
  return `rounded-full px-3 py-2 text-sm transition ${
    isActive ? 'bg-soft text-mist' : 'text-muted hover:bg-soft hover:text-mist'
  }`;
}

export function PublicHeader() {
  const { user, logout } = useAuth();
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const mobileNavRef = useRef<HTMLElement>(null);
  const closeMobile = useCallback(() => setOpen(false), []);
  useFocusTrap(open, mobileNavRef, closeMobile);

  const nav = (
    <>
      <NavLink to="/" end className={({ isActive }) => linkClass(isActive)} onClick={() => setOpen(false)}>
        {t('nav.home')}
      </NavLink>
      <NavLink
        to="/caregivers"
        className={({ isActive }) => linkClass(isActive)}
        onClick={() => setOpen(false)}
      >
        {t('nav.caregivers')}
      </NavLink>
      <NavLink
        to="/catalog"
        className={({ isActive }) => linkClass(isActive)}
        onClick={() => setOpen(false)}
      >
        {t('nav.packages')}
      </NavLink>
      <NavLink
        to="/contact"
        className={({ isActive }) => linkClass(isActive)}
        onClick={() => setOpen(false)}
      >
        {t('nav.contact')}
      </NavLink>
      {user && (
        <>
          <NavLink
            to="/platform"
            className={({ isActive }) => linkClass(isActive)}
            onClick={() => setOpen(false)}
          >
            {t('nav.app')}
          </NavLink>
          <NavLink
            to="/messages"
            className={({ isActive }) => linkClass(isActive)}
            onClick={() => setOpen(false)}
          >
            {t('nav.messages')}
          </NavLink>
          <NavLink
            to="/account"
            className={({ isActive }) => linkClass(isActive)}
            onClick={() => setOpen(false)}
          >
            {t('nav.account')}
          </NavLink>
        </>
      )}
    </>
  );

  return (
    <header className="sticky top-0 z-20 -mx-5 border-b border-hair/80 bg-panel/90 px-5 py-3 backdrop-blur-xl sm:-mx-8 sm:px-8">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4">
        <Link to="/" className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-cyan" aria-hidden />
          <span className="font-display text-lg text-mist">{brand.name}</span>
        </Link>
        <nav className="hidden items-center gap-1 md:flex" aria-label="Primary">
          {nav}
        </nav>
        <div className="flex items-center gap-2">
          <LanguageSwitcher />
          <ThemeToggle />
          {user ? (
            <>
              <Link to="/platform" className="hidden sm:block">
                <Button tone="ghost" className="min-h-10 px-3 py-1.5">
                  {t('action.openApp')}
                </Button>
              </Link>
              <Button tone="danger" className="min-h-10 px-3 py-1.5" onClick={logout}>
                {t('action.signOut')}
              </Button>
            </>
          ) : (
            <>
              <Link to="/login">
                <Button tone="ghost" className="min-h-10 px-3 py-1.5">
                  {t('action.signIn')}
                </Button>
              </Link>
              <Link to="/register" className="hidden sm:block">
                <Button className="min-h-10 px-3 py-1.5">{t('action.getStarted')}</Button>
              </Link>
            </>
          )}
          <button
            type="button"
            className="rounded-full border border-hair px-3 py-1.5 text-xs text-muted md:hidden"
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
          className="mt-3 flex flex-col gap-1 border-t border-hair pt-3 md:hidden"
          aria-label="Mobile primary"
        >
          {nav}
        </nav>
      )}
    </header>
  );
}
