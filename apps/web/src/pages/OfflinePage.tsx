import { WifiOff } from 'lucide-react';
import { Link } from 'react-router-dom';

/** Explicit offline surface so a hard reload without network is not a blank screen (Step 93). */
export function OfflinePage() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center px-6 py-16 text-center">
      <WifiOff className="mb-4 h-10 w-10 text-cyan" aria-hidden />
      <h1 className="text-2xl font-semibold text-primary">You’re offline</h1>
      <p className="mt-3 text-sm text-muted">
        Care Plus can still open from the installed app shell. Reconnect to load live matches,
        messages, and care requests.
      </p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          className="rounded-lg bg-cyan px-4 py-2 text-sm font-semibold text-inverse"
          onClick={() => window.location.assign('/')}
        >
          Try again
        </button>
        <Link to="/" className="text-sm text-cyan underline-offset-2 hover:underline">
          Go home
        </Link>
      </div>
    </div>
  );
}
