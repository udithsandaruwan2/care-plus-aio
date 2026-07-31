import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { Lead } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { PageHeader } from '../components/ui/PageHeader';

const STATUS_LABEL: Record<string, string> = {
  new: 'New',
  contacted: 'Contacted',
  closed: 'Closed',
};

const FILTERS = ['', 'new', 'contacted', 'closed'] as const;

/** Admin marketing leads queue (Steps 27 + 57). */
export function LeadsPage() {
  const { user } = useAuth();
  const [rows, setRows] = useState<Lead[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [notesById, setNotesById] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .listLeads(undefined, statusFilter || undefined)
      .then((data) => setRows(data.results))
      .catch((err) => {
        setRows([]);
        setError(err instanceof Error ? err.message : 'Could not load leads.');
      })
      .finally(() => setLoading(false));
  }, [statusFilter]);

  useEffect(() => {
    if (user?.role === 'admin') load();
    else setLoading(false);
  }, [user?.role, load]);

  async function onContact(id: number) {
    setBusyId(id);
    setError(null);
    try {
      const updated = await api.markLeadContacted(id, notesById[id]);
      setRows((prev) => prev.map((r) => (r.id === id ? updated : r)));
      setNotesById((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update lead.');
    } finally {
      setBusyId(null);
    }
  }

  async function onClose(id: number) {
    setBusyId(id);
    setError(null);
    try {
      const updated = await api.closeLead(id, notesById[id]);
      setRows((prev) => {
        if (statusFilter && statusFilter !== 'closed') {
          return prev.filter((r) => r.id !== id);
        }
        return prev.map((r) => (r.id === id ? updated : r));
      });
      setNotesById((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not close lead.');
    } finally {
      setBusyId(null);
    }
  }

  if (user?.role !== 'admin') {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-col">
        <p className="text-sm text-muted">Admin access required for the leads queue.</p>
        <Link to="/platform" className="mt-4 inline-block text-sm text-cyan hover:underline">
          Back home
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col">
      <PageHeader
        eyebrow="Admin"
        title="Marketing leads"
        subtitle="Process contact-form enquiries: contact, note, and close."
      />

      <div className="mt-6 flex flex-wrap gap-2">
        {FILTERS.map((value) => (
          <button
            key={value || 'all'}
            type="button"
            onClick={() => setStatusFilter(value)}
            className={`rounded-full border px-3 py-1.5 text-xs transition ${
              statusFilter === value
                ? 'border-cyan/50 bg-cyan/10 text-cyan'
                : 'border-hair text-muted hover:border-cyan/40 hover:text-mist'
            }`}
          >
            {value ? STATUS_LABEL[value] : 'All'}
          </button>
        ))}
      </div>

      {loading && <p className="mt-8 text-sm text-muted">Loading…</p>}
      {error && (
        <p className="mt-6 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
          {error}
        </p>
      )}
      {!loading && rows.length === 0 && (
        <p className="mt-8 text-sm text-muted">
          No leads in this filter — submissions appear from /contact.
        </p>
      )}

      <ul className="mt-8 space-y-3">
        {rows.map((row) => {
          const open = row.status === 'new' || row.status === 'contacted';
          return (
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
                    {row.source ? ` · ${row.source}` : ''}
                  </p>
                  <p className="mt-1 text-xs text-cyan">
                    {row.email}
                    {row.phone ? ` · ${row.phone}` : ''}
                  </p>
                </div>
              </div>
              {row.message && <p className="mt-3 text-sm text-mist/90">{row.message}</p>}
              {row.admin_notes && (
                <p className="mt-2 text-xs text-muted">Notes: {row.admin_notes}</p>
              )}
              {open && (
                <div className="mt-4 space-y-3">
                  <Input
                    placeholder="Admin notes (optional)"
                    value={notesById[row.id] ?? ''}
                    onChange={(e) =>
                      setNotesById((prev) => ({ ...prev, [row.id]: e.target.value }))
                    }
                  />
                  <div className="flex flex-wrap gap-2">
                    {row.status === 'new' && (
                      <Button
                        className="min-h-9 px-3 py-1.5 text-xs"
                        disabled={busyId === row.id}
                        onClick={() => void onContact(row.id)}
                      >
                        {busyId === row.id ? 'Saving…' : 'Mark contacted'}
                      </Button>
                    )}
                    <Button
                      tone="ghost"
                      className="min-h-9 px-3 py-1.5 text-xs"
                      disabled={busyId === row.id}
                      onClick={() => void onClose(row.id)}
                    >
                      Close lead
                    </Button>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
