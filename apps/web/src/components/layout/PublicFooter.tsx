import { Link } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { SUPPORT_EMAIL } from '../../config';

export function PublicFooter() {
  const { user } = useAuth();

  return (
    <footer className="border-t border-hair bg-void py-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
        <p>© {new Date().getFullYear()} Care Plus Sri Lanka. All rights reserved.</p>
        <div className="flex flex-wrap gap-6">
          <Link to="/privacy" className="hover:text-cyan">
            PDPA Privacy Policy
          </Link>
          <Link to="/contact" className="hover:text-cyan">
            Contact Support
          </Link>
          <a href={`mailto:${SUPPORT_EMAIL}`} className="hover:text-cyan">
            {SUPPORT_EMAIL}
          </a>
          {user ? (
            <Link to="/hub" className="hover:text-cyan">
              Open app
            </Link>
          ) : (
            <Link to="/login" className="hover:text-cyan">
              Log In
            </Link>
          )}
        </div>
      </div>
    </footer>
  );
}
