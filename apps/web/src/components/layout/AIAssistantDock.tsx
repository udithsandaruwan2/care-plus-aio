import { Link } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';

export function AIAssistantDock() {
  const { user } = useAuth();
  const target = user ? '/app' : '/login';
  return (
    <div className="fixed bottom-5 right-5 z-30 w-[18rem] rounded-3xl border border-cyan/30 bg-panel/95 p-3 shadow-[var(--cp-shadow-soft)] backdrop-blur-xl">
      <p className="font-display text-sm text-cyan">AI Assistant</p>
      <p className="mt-1 text-xs text-muted">
        Ask Serah for caregiver recommendations in Sinhala, Tamil, or English.
      </p>
      <Link
        to={target}
        className="mt-3 block rounded-full bg-cyan px-3 py-2 text-center text-xs font-medium text-inverse hover:brightness-95"
      >
        {user ? 'Open assistant' : 'Sign in to chat'}
      </Link>
    </div>
  );
}

