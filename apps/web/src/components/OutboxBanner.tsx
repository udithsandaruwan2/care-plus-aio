import { Link } from 'react-router-dom';
import { dismissFailedOutbox, flushOutbox, retryOutboxItem } from '../lib/outbox/flush';
import { pendingOutboxCount, useOutboxStore } from '../lib/outbox/outboxStore';

/** Visible pending / failed queued writes (Step 95). */
export function OutboxBanner() {
  const items = useOutboxStore((s) => s.items);
  const pending = pendingOutboxCount(items);
  const failed = items.filter((i) => i.status === 'failed');

  if (pending === 0 && failed.length === 0) return null;

  return (
    <div
      role="status"
      className="border-b border-teal-700/25 bg-teal-950/70 px-4 py-2 text-center text-sm text-teal-50"
    >
      {pending > 0 && (
        <span>
          {pending} pending {pending === 1 ? 'send' : 'sends'} waiting to sync
          {typeof navigator !== 'undefined' && navigator.onLine ? (
            <>
              .{' '}
              <button
                type="button"
                className="font-medium underline underline-offset-2"
                onClick={() => void flushOutbox()}
              >
                Retry now
              </button>
            </>
          ) : (
            <> — will send when you reconnect.</>
          )}
        </span>
      )}
      {failed.length > 0 && (
        <span className={pending > 0 ? ' ml-2 block sm:ml-3 sm:inline' : undefined}>
          {failed.length} failed:{' '}
          {failed.slice(0, 2).map((f) => (
            <span key={f.id} className="mr-2">
              {f.label || f.kind}
              {f.permanent ? (
                <button
                  type="button"
                  className="ml-1 underline underline-offset-2"
                  onClick={() => void dismissFailedOutbox(f.id)}
                >
                  dismiss
                </button>
              ) : (
                <button
                  type="button"
                  className="ml-1 underline underline-offset-2"
                  onClick={() => void retryOutboxItem(f.id)}
                >
                  retry
                </button>
              )}
            </span>
          ))}
          {failed.some((f) => f.kind === 'care_request') && (
            <Link to="/requests" className="ml-1 underline underline-offset-2">
              Requests
            </Link>
          )}
        </span>
      )}
    </div>
  );
}
