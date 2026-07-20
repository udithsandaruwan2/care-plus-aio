import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { Lead } from '@care-plus/api-client';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';

const STATUS_LABEL: Record<string, string> = {
  new: 'New',
  contacted: 'Contacted',
  closed: 'Closed',
};

/** Admin marketing leads queue (Step 27). */
export function LeadsPage() {
  const { user, logout } = useAuth();
  const [rows, setRows] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .listLeads()
      .then((data) => setRows(data.results))
      .catch((err) => {
        setRows([]);
        setError(err instanceof Error ? err.message : 'Could not load leads.');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (user?.role === 'admin') load();
    else setLoading(false);
  }, [user?.role, load]);

  async function onContact(id: number) {
    const notes = window.prompt('Optional notes:') ?? '';
    setBusyId(id);
    try {
      const updated = await api.markLeadContacted(id, notes.trim() || undefined);
      setRows((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not mark contacted.');
    } finally {
      setBusyId(null);
    }
  }

  if (user?.role !== 'admin') {
    return (
      <AtmosphereShell>
        <main className="mx-auto max-w-lg px-6 py-16">
          <p className="text-sm text-muted">Admin access required for the leads queue.</p>
          <Link to="/" className="mt-4 inline-block text-sm text-cyan hover:underline">
            Back home
          </Link>
        </main>
      </AtmosphereShell>
    );
  }

  return (
    <AtmosphereShell>
      <main className="mx-auto flex min-h-full max-w-3xl flex-col px-6 py-10">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-display text-sm uppercase tracking-[0.2em] text-cyan">Admin</p>
            <h1 className="mt-2 font-display text-3xl font-semibold text-mist">Marketing leads</h1>
          </div>
          <div className="flex gap-2">
            <Link
              to="/"
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted hover:border-cyan hover:text-cyan"
            >
              Home
            </Link>
            <button
              type="button"
              onClick={logout}
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted hover:border-rose hover:text-rose"
            >
              Sign out
            </button>
          </div>
        </div>

        {loading && <p className="mt-8 text-sm text-muted">Loading…</p>}
        {error && (
          <p className="mt-8 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
            {error}
          </p>
        )}
        {!loading && rows.length === 0 && (
          <p className="mt-8 text-sm text-muted">No leads yet — submissions appear from /contact.</p>
        )}

        <ul className="mt-8 space-y-3">
          {rows.map((row) => (
            <li
              key={row.id}
              className="rounded-2xl border border-hair bg-panel/70 p-5 backdrop-blur-md"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-display text-lg text-mist">{row.name}</p>
                  <p className="mt-1 text-xs text-muted">
                    {STATUS_LABEL[row.status] || row.status}
                    {row.city ? ` · ${row.city}` : ''}
                    {row.preferred_language ? ` · ${row.preferred_language}` : ''}
                  </p>
                  <p className="mt-1 text-xs text-cyan">
                    {row.email}
                    {row.phone ? ` · ${row.phone}` : ''}
                  </p>
                </div>
                {row.status === 'new' && (
                  <button
                    type="button"
                    disabled={busyId === row.id}
                    onClick={() => void onContact(row.id)}
                    className="rounded-lg border border-mint/50 px-3 py-1.5 text-xs text-mint hover:bg-mint/10 disabled:opacity-50"
                  >
                    Mark contacted
                  </button>
                )}
              </div>
              {row.message && <p className="mt-3 text-sm text-mist/90">{row.message}</p>}
              {row.admin_notes && (
                <p className="mt-2 text-xs text-muted">Notes: {row.admin_notes}</p>
              )}
            </li>
          ))}
        </ul>
      </main>
    </AtmosphereShell>
  );
}
