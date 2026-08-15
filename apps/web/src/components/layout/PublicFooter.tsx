import { Link } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { SUPPORT_EMAIL } from '../../config';

export function PublicFooter() {
  const { user } = useAuth();

  return (
    <footer className="mt-12 border-t border-hair/80 py-8">
      <div className="grid gap-6 text-sm text-muted md:grid-cols-3">
        <div>
          <p className="font-display text-base text-mist">Care Plus Sri Lanka</p>
          <p className="mt-2">
            Colombo operations with caregiver onboarding across Kandy, Galle, and Kurunegala.
          </p>
        </div>
        <div>
          <p className="font-display text-base text-mist">Platform</p>
          <div className="mt-2 flex flex-col gap-1">
            <Link to="/caregivers" className="hover:text-cyan">
              Browse caregivers
            </Link>
            <Link to="/catalog" className="hover:text-cyan">
              Packages
            </Link>
            <Link to="/contact" className="hover:text-cyan">
              Contact
            </Link>
            <Link to="/privacy" className="hover:text-cyan">
              Privacy (PDPA)
            </Link>
            {user ? (
              <Link to="/platform" className="hover:text-cyan">
                Open app
              </Link>
            ) : (
              <Link to="/login" className="hover:text-cyan">
                Sign in
              </Link>
            )}
          </div>
        </div>
        <div>
          <p className="font-display text-base text-mist">Support</p>
          <p className="mt-2">
            Email:{' '}
            <a className="hover:text-cyan" href={`mailto:${SUPPORT_EMAIL}`}>
              {SUPPORT_EMAIL}
            </a>
          </p>
          <p className="mt-2 text-xs">Mon–Sat, 8:00 AM – 8:00 PM (Asia/Colombo)</p>
        </div>
      </div>
      <p className="mt-6 text-xs text-muted">© {new Date().getFullYear()} Care Plus. All rights reserved.</p>
    </footer>
  );
}
