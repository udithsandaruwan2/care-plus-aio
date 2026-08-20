import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

/** Compact banner when the browser reports offline (Step 93). */
export function OfflineBanner() {
  const [offline, setOffline] = useState(
    () => typeof navigator !== 'undefined' && navigator.onLine === false,
  );

  useEffect(() => {
    const goOffline = () => setOffline(true);
    const goOnline = () => setOffline(false);
    window.addEventListener('offline', goOffline);
    window.addEventListener('online', goOnline);
    return () => {
      window.removeEventListener('offline', goOffline);
      window.removeEventListener('online', goOnline);
    };
  }, []);

  if (!offline) return null;

  return (
    <div
      role="status"
      className="border-b border-amber-500/30 bg-amber-950/80 px-4 py-2 text-center text-sm text-amber-100"
    >
      You’re offline.{' '}
      <Link to="/offline" className="font-medium underline underline-offset-2">
        Offline help
      </Link>
    </div>
  );
}
