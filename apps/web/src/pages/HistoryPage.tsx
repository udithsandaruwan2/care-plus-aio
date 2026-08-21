import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import type { MatchHistoryEntry } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { PageHeader } from '../components/ui/PageHeader';
import { Button } from '../components/ui/Button';

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

type SessionGroup = {
  key: string;
  label: string;
  entries: MatchHistoryEntry[];
};

function groupBySession(entries: MatchHistoryEntry[]): SessionGroup[] {
  const map = new Map<string, SessionGroup>();
  for (const entry of entries) {
    const sid = entry.session?.id;
    const key = sid != null ? `session-${sid}` : `run-${entry.id}`;
    const label =
      sid != null
        ? `Conversation #${sid}${entry.session?.active ? ' (active)' : ''}`
        : 'Direct search';
    const group = map.get(key) ?? { key, label, entries: [] };
    group.entries.push(entry);
    map.set(key, group);
  }
  return Array.from(map.values());
}

export function HistoryPage() {
  const { user } = useAuth();
  const [rows, setRows] = useState<MatchHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .listMatchHistory()
      .then((data) => setRows(data.results))
      .catch((err) => {
        setRows([]);
        setError(err instanceof Error ? err.message : 'Could not load history.');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (user?.role === 'patient') load();
    else setLoading(false);
  }, [user?.role, load]);

  const groups = useMemo(() => groupBySession(rows), [rows]);

  async function onDelete(id: number) {
    if (!window.confirm('Remove this search from your history? This cannot be undone.')) return;
    setBusyId(id);
    setError(null);
    try {
      await api.deleteMatchHistory(id);
      setRows((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete entry.');
    } finally {
      setBusyId(null);
    }
  }

  if (user && user.role !== 'patient') {
    return <Navigate to="/hub" replace />;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
      <PageHeader
        title="Search history"
        subtitle="Past Serah matches with who was recommended and why. Delete any entry to remove it from your account and future exports."
      />

      {error && (
        <p className="rounded-lg border border-rose/40 bg-rose/10 px-3 py-2 text-sm text-rose" role="alert">
          {error}
        </p>
      )}

      {loading && <p className="text-sm text-muted">Loading history…</p>}

      {!loading && rows.length === 0 && (
        <p className="text-sm text-muted">
          No searches yet.{' '}
          <Link to="/app" className="text-cyan underline-offset-2 hover:underline">
            Talk to Serah
          </Link>{' '}
          to find caregivers.
        </p>
      )}

      {groups.map((group) => (
        <section key={group.key} className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">{group.label}</h2>
          {group.entries.map((entry) => {
            const open = expanded[entry.id] ?? false;
            const title =
              entry.condition ||
              entry.understood?.condition ||
              entry.query ||
              'Care search';
            return (
              <article
                key={entry.id}
                className="rounded-[16px] border border-hair bg-panel/80 px-4 py-4 shadow-[var(--cp-shadow-soft)]"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-mist">{title}</p>
                    <p className="mt-1 text-xs text-muted">
                      {formatWhen(entry.created_at)}
                      {entry.language ? ` · ${entry.language}` : ''}
                      {entry.care_level ? ` · ${entry.care_level}` : ''}
                      {entry.emergency ? ' · Emergency' : ''}
                    </p>
                    {entry.understood?.raw_text ? (
                      <p className="mt-2 text-sm text-mist/90">
                        Serah heard: “{entry.understood.raw_text}”
                      </p>
                    ) : entry.query ? (
                      <p className="mt-2 text-sm text-mist/90">Query: {entry.query}</p>
                    ) : null}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      tone="ghost"
                      onClick={() =>
                        setExpanded((prev) => ({ ...prev, [entry.id]: !open }))
                      }
                    >
                      {open ? 'Hide results' : `Results (${entry.results.length})`}
                    </Button>
                    <Button
                      type="button"
                      tone="danger"
                      disabled={busyId === entry.id}
                      onClick={() => onDelete(entry.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </div>

                {open && (
                  <ul className="mt-4 space-y-3 border-t border-hair pt-4">
                    {entry.results.length === 0 && (
                      <li className="text-sm text-muted">No caregivers were ranked.</li>
                    )}
                    {entry.results.map((hit) => (
                      <li key={`${entry.id}-${hit.caregiver_id}-${hit.rank}`} className="text-sm">
                        <div className="flex flex-wrap items-baseline gap-2">
                          <span className="font-medium text-mist">
                            #{hit.rank}{' '}
                            <Link
                              to={`/caregivers/${hit.caregiver_id}`}
                              className="text-cyan underline-offset-2 hover:underline"
                            >
                              {hit.display_name || `Caregiver #${hit.caregiver_id}`}
                            </Link>
                          </span>
                          <span className="text-xs text-muted">score {hit.score.toFixed(3)}</span>
                        </div>
                        {hit.explanation && (
                          <p className="mt-1 text-muted">{hit.explanation}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}

                {entry.outcomes.length > 0 && (
                  <div className="mt-3 border-t border-hair pt-3 text-sm text-muted">
                    What happened next:{' '}
                    {entry.outcomes.map((o) => (
                      <span key={o.care_request_id} className="mr-2">
                        {o.caregiver_name || `Caregiver #${o.caregiver_id}`} — {o.status}
                      </span>
                    ))}
                    <Link to="/requests" className="text-cyan underline-offset-2 hover:underline">
                      View requests
                    </Link>
                  </div>
                )}
              </article>
            );
          })}
        </section>
      ))}
    </div>
  );
}
