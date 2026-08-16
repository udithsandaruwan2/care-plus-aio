import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AUDIT_ACTIONS, type AuditLog } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { PageHeader } from '../components/ui/PageHeader';

/** Admin/auditor audit log browser with filters + CSV (Step 58). */
export function AdminAuditPage() {
  const { user } = useAuth();
  const canRead = user?.role === 'admin' || user?.role === 'auditor';

  const [rows, setRows] = useState<AuditLog[]>([]);
  const [count, setCount] = useState(0);
  const [actor, setActor] = useState('');
  const [action, setAction] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const filters = {
    actor: actor.trim() || undefined,
    action: action || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    page_size: 50,
  };

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .listAuditLogs(filters)
      .then((data) => {
        setRows(data.results);
        setCount(data.count);
      })
      .catch((err) => {
        setRows([]);
        setCount(0);
        setError(err instanceof Error ? err.message : 'Could not load audit log.');
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional filter snapshot on Apply
  }, [actor, action, dateFrom, dateTo]);

  useEffect(() => {
    if (canRead) load();
    else setLoading(false);
  }, [canRead, load]);

  async function onExport() {
    setExporting(true);
    setError(null);
    try {
      const csv = await api.exportAuditLogsCsv(filters);
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'careplus-audit.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed.');
    } finally {
      setExporting(false);
    }
  }

  if (!canRead) {
    return (
      <div className="mx-auto max-w-3xl">
        <p className="text-sm text-muted">Admin or auditor access required.</p>
        <Link to="/hub" className="mt-4 inline-block text-sm text-cyan hover:underline">
          Back home
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col">
      <PageHeader
        eyebrow="Admin"
        title="Audit log"
        subtitle="Filter by actor, action, and date; export CSV for compliance review."
      />

      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="block space-y-1.5">
          <span className="text-xs uppercase tracking-wide text-muted">Actor (email or id)</span>
          <Input value={actor} onChange={(e) => setActor(e.target.value)} placeholder="admin@…" />
        </label>
        <label className="block space-y-1.5">
          <span className="text-xs uppercase tracking-wide text-muted">Action</span>
          <select
            className="min-h-11 w-full rounded-2xl border border-hair bg-elevated px-3 text-sm text-mist"
            value={action}
            onChange={(e) => setAction(e.target.value)}
          >
            <option value="">All actions</option>
            {AUDIT_ACTIONS.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </label>
        <label className="block space-y-1.5">
          <span className="text-xs uppercase tracking-wide text-muted">From</span>
          <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label className="block space-y-1.5">
          <span className="text-xs uppercase tracking-wide text-muted">To</span>
          <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button className="min-h-9 px-3 py-1.5 text-xs" onClick={() => load()} disabled={loading}>
          Apply filters
        </Button>
        <Button
          tone="ghost"
          className="min-h-9 px-3 py-1.5 text-xs"
          disabled={exporting}
          onClick={() => void onExport()}
        >
          {exporting ? 'Exporting…' : 'Export CSV'}
        </Button>
      </div>

      {loading && <p className="mt-8 text-sm text-muted">Loading audit rows…</p>}
      {error && (
        <p className="mt-6 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
          {error}
        </p>
      )}

      {!loading && (
        <p className="mt-6 text-xs text-muted">
          Showing {rows.length} of {count} matching row(s).
        </p>
      )}

      <ul className="mt-4 space-y-2">
        {rows.map((row) => (
          <li key={row.id} className="rounded-xl border border-hair bg-panel/60 px-4 py-3 text-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-display text-mist">{row.action}</p>
              <p className="text-xs text-muted">{formatTs(row.ts)}</p>
            </div>
            <p className="mt-1 text-xs text-muted">
              {row.actor_email || (row.actor != null ? `user #${row.actor}` : 'system')}
              {row.ip ? ` · ${row.ip}` : ''}
              {row.target_type
                ? ` · ${row.target_type}${row.target_id ? `#${row.target_id}` : ''}`
                : ''}
            </p>
          </li>
        ))}
      </ul>

      {!loading && rows.length === 0 && (
        <p className="mt-6 text-sm text-muted">No audit rows match these filters.</p>
      )}
    </div>
  );
}

function formatTs(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat('en-LK', {
    timeZone: 'Asia/Colombo',
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(d);
}
