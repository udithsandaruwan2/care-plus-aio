import { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { brand } from '@care-plus/ui-tokens';
import { useAuth } from '../../auth/AuthContext';
import { ThemeToggle } from '../../theme/ThemeToggle';
import { Button } from '../ui/Button';

function linkClass(isActive: boolean) {
  return `rounded-full px-3 py-2 text-sm transition ${
    isActive ? 'bg-soft text-mist' : 'text-muted hover:bg-soft hover:text-mist'
  }`;
}

export function PublicHeader() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);

  const nav = (
    <>
      <NavLink to="/" end className={({ isActive }) => linkClass(isActive)} onClick={() => setOpen(false)}>
        Home
      </NavLink>
      <NavLink
        to="/caregivers"
        className={({ isActive }) => linkClass(isActive)}
        onClick={() => setOpen(false)}
      >
        Caregivers
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
        <>
          <NavLink
            to="/platform"
            className={({ isActive }) => linkClass(isActive)}
            onClick={() => setOpen(false)}
          >
            App
          </NavLink>
          <NavLink
            to="/messages"
            className={({ isActive }) => linkClass(isActive)}
            onClick={() => setOpen(false)}
          >
            Messages
          </NavLink>
          <NavLink
            to="/account"
            className={({ isActive }) => linkClass(isActive)}
            onClick={() => setOpen(false)}
          >
            Account
          </NavLink>
        </>
      )}
    </>
  );

  return (
    <header className="sticky top-0 z-20 -mx-5 border-b border-hair/80 bg-panel/90 px-5 py-3 backdrop-blur-xl sm:-mx-8 sm:px-8">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4">
        <Link to="/" className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-cyan" />
          <span className="font-display text-lg text-mist">{brand.name}</span>
        </Link>
        <nav className="hidden items-center gap-1 md:flex">{nav}</nav>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          {user ? (
            <>
              <Link to="/platform" className="hidden sm:block">
                <Button tone="ghost" className="min-h-10 px-3 py-1.5">
                  Open app
                </Button>
              </Link>
              <Button tone="danger" className="min-h-10 px-3 py-1.5" onClick={logout}>
                Sign out
              </Button>
            </>
          ) : (
            <>
              <Link to="/login">
                <Button tone="ghost" className="min-h-10 px-3 py-1.5">
                  Sign in
                </Button>
              </Link>
              <Link to="/register" className="hidden sm:block">
                <Button className="min-h-10 px-3 py-1.5">Get started</Button>
              </Link>
            </>
          )}
          <button
            type="button"
            className="rounded-full border border-hair px-3 py-1.5 text-xs text-muted md:hidden"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
          >
            Menu
          </button>
        </div>
      </div>
      {open && (
        <nav className="mt-3 flex flex-col gap-1 border-t border-hair pt-3 md:hidden">{nav}</nav>
      )}
    </header>
  );
}
