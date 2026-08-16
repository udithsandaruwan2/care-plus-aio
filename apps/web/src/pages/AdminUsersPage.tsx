import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { AdminUser } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/ui/Button';
import { PageHeader } from '../components/ui/PageHeader';

const ROLES = ['', 'patient', 'caregiver', 'admin', 'auditor'] as const;

/** Admin/auditor user directory — disable is admin-only (Step 54). */
export function AdminUsersPage() {
  const { user } = useAuth();
  const canWrite = user?.role === 'admin';
  const canRead = user?.role === 'admin' || user?.role === 'auditor';

  const [rows, setRows] = useState<AdminUser[]>([]);
  const [role, setRole] = useState('');
  const [activeOnly, setActiveOnly] = useState<'all' | 'true' | 'false'>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .listAdminUsers({
        role: role || undefined,
        is_active: activeOnly === 'all' ? undefined : activeOnly === 'true',
        page_size: 50,
      })
      .then((data) => setRows(data.results))
      .catch((err) => {
        setRows([]);
        setError(err instanceof Error ? err.message : 'Could not load users.');
      })
      .finally(() => setLoading(false));
  }, [role, activeOnly]);

  useEffect(() => {
    if (canRead) load();
    else setLoading(false);
  }, [canRead, load]);

  async function onToggleActive(row: AdminUser) {
    if (!canWrite || busyId != null) return;
    if (row.id === user?.id) {
      setError('You cannot disable your own account.');
      return;
    }
    setBusyId(row.id);
    setError(null);
    try {
      const updated = await api.setAdminUserActive(row.id, !row.is_active);
      setRows((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update account.');
    } finally {
      setBusyId(null);
    }
  }

  if (!canRead) {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-col">
        <p className="text-sm text-muted">Admin or auditor access required.</p>
        <Link to="/hub" className="mt-4 inline-block text-sm text-cyan hover:underline">
          Back home
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col">
      <PageHeader
        eyebrow="Admin"
        title="Users"
        subtitle={
          canWrite
            ? 'Filter by role and disable accounts. Auditors can view only.'
            : 'Read-only user directory (auditor).'
        }
      />

      <div className="mt-6 flex flex-wrap gap-2">
        {ROLES.map((r) => (
          <button
            key={r || 'all'}
            type="button"
            onClick={() => setRole(r)}
            className={`rounded-full border px-3 py-1.5 text-xs transition ${
              role === r
                ? 'border-cyan/50 bg-cyan/10 text-cyan'
                : 'border-hair text-muted hover:border-cyan/40 hover:text-mist'
            }`}
          >
            {r || 'All roles'}
          </button>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {(
          [
            ['all', 'All status'],
            ['true', 'Active'],
            ['false', 'Disabled'],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setActiveOnly(value)}
            className={`rounded-full border px-3 py-1.5 text-xs transition ${
              activeOnly === value
                ? 'border-cyan/50 bg-cyan/10 text-cyan'
                : 'border-hair text-muted hover:border-cyan/40 hover:text-mist'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {loading && <p className="mt-8 text-sm text-muted">Loading users…</p>}
      {error && (
        <p className="mt-6 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
          {error}
        </p>
      )}

      <ul className="mt-6 space-y-3">
        {rows.map((row) => (
          <li
            key={row.id}
            className="flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-hair bg-panel/70 p-4"
          >
            <div>
              <p className="font-display text-mist">{row.email}</p>
              <p className="mt-1 text-xs text-muted">
                {row.role}
                {row.first_name || row.last_name
                  ? ` · ${[row.first_name, row.last_name].filter(Boolean).join(' ')}`
                  : ''}
                {' · '}
                {row.is_active ? (
                  <span className="text-mint">active</span>
                ) : (
                  <span className="text-rose">disabled</span>
                )}
              </p>
            </div>
            {canWrite && (
              <Button
                tone={row.is_active ? 'danger' : 'ghost'}
                className="min-h-9 px-3 py-1.5 text-xs"
                disabled={busyId === row.id || row.id === user?.id}
                onClick={() => void onToggleActive(row)}
              >
                {busyId === row.id ? 'Saving…' : row.is_active ? 'Disable' : 'Enable'}
              </Button>
            )}
          </li>
        ))}
      </ul>

      {!loading && rows.length === 0 && (
        <p className="mt-6 text-sm text-muted">No users match these filters.</p>
      )}
    </div>
  );
}
