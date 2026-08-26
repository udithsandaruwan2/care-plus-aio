import { useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { AdminAnalytics } from '@care-plus/api-client';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { PageHeader } from '../components/ui/PageHeader';

const COLORS = ['#2dd4bf', '#38bdf8', '#a3e635', '#fbbf24', '#fb7185', '#c084fc'];

/** Admin/auditor analytics dashboard (Step 56). */
export function AdminAnalyticsPage() {
  const { user } = useAuth();
  const canRead = user?.role === 'admin' || user?.role === 'auditor';
  const [data, setData] = useState<AdminAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!canRead) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api
      .getAdminAnalytics(30)
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((err) => {
        if (!cancelled) {
          setData(null);
          setError(err instanceof Error ? err.message : 'Could not load analytics.');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [canRead]);

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
        title="Analytics"
        subtitle="Requests by status, role distribution, match latency, and care relationships."
      />

      {loading && <p className="mt-8 text-sm text-muted">Loading analytics…</p>}
      {error && (
        <p className="mt-6 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
          {error}
        </p>
      )}

      {data && (
        <div className="mt-8 grid gap-8 lg:grid-cols-2">
          <ChartCard title="Care requests by status">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={data.requests_by_status}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                <XAxis dataKey="label" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#2dd4bf" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Users by role">
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={data.roles}
                  dataKey="count"
                  nameKey="label"
                  innerRadius={50}
                  outerRadius={90}
                  paddingAngle={2}
                >
                  {data.roles.map((entry, i) => (
                    <Cell key={entry.key} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title={`Match latency — VEHMF engine (last ${data.match_latency.window_days}d)`}>
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
              <Metric label="Samples" value={String(data.match_latency.sample_size)} />
              <Metric label="p50" value={fmtMs(data.match_latency.p50_ms)} />
              <Metric label="p95" value={fmtMs(data.match_latency.p95_ms)} />
              <Metric label="p99" value={fmtMs(data.match_latency.p99_ms)} />
              <Metric label="avg" value={fmtMs(data.match_latency.avg_ms)} />
            </dl>
          </ChartCard>

          {data.turn_latency ? (
            <ChartCard title={`Voice turn latency (last ${data.turn_latency.window_days}d)`}>
              <p className="mb-3 text-xs text-muted">
                Full <code>/voice/turn/</code> wall time (ASR + intent + route + match + chat + TTS).
                Distinct from VEHMF engine time above. Watch <strong>chat p95</strong> — spikes over
                ~8s fall back to stub replies so the client does not show a false timeout.
              </p>
              <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                <Metric label="Samples" value={String(data.turn_latency.sample_size)} />
                <Metric label="total p50" value={fmtMs(data.turn_latency.p50_ms)} />
                <Metric label="total p95" value={fmtMs(data.turn_latency.p95_ms)} />
                <Metric label="total p99" value={fmtMs(data.turn_latency.p99_ms)} />
                <Metric label="avg" value={fmtMs(data.turn_latency.avg_ms)} />
              </dl>
              {data.turn_latency.stages && Object.keys(data.turn_latency.stages).length > 0 ? (
                <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                  {['asr_ms', 'intent_ms', 'route_ms', 'match_ms', 'chat_ms', 'tts_ms'].map((key) => (
                    <Metric
                      key={key}
                      label={`${key.replace('_ms', '')} p95`}
                      value={fmtMs(data.turn_latency?.stages?.[key]?.p95_ms ?? null)}
                    />
                  ))}
                </dl>
              ) : null}
            </ChartCard>
          ) : null}

          <ChartCard title="Care relationships">
            <p className="mb-3 text-sm text-muted">
              Active now: <span className="text-mint">{data.relationships.active}</span>
            </p>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={data.relationships.by_status}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                <XAxis dataKey="label" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#38bdf8" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          {data.weight_ab ? (
            <ChartCard title={`Weight A/B — ${data.weight_ab.experiment_id}`}>
              <p className="mb-3 text-sm text-muted">
                {data.weight_ab.stopping_rule.ready ? (
                  <span className="text-mint">{data.weight_ab.stopping_rule.guidance}</span>
                ) : (
                  <span className="text-amber-200">{data.weight_ab.stopping_rule.guidance}</span>
                )}
              </p>
              {data.weight_ab.variants.length === 0 ? (
                <p className="text-sm text-muted">No variant-tagged MatchRuns in this window.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm text-mist">
                    <thead className="text-[11px] uppercase tracking-wide text-muted">
                      <tr>
                        <th className="py-2 pr-3">Variant</th>
                        <th className="py-2 pr-3">n</th>
                        <th className="py-2 pr-3">Accept</th>
                        <th className="py-2 pr-3">Complete</th>
                        <th className="py-2">TTA p50</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.weight_ab.variants.map((row) => (
                        <tr key={row.variant} className="border-t border-hair/60">
                          <td className="py-2 pr-3 font-medium">{row.variant}</td>
                          <td className="py-2 pr-3">{row.n_runs}</td>
                          <td className="py-2 pr-3">
                            {(row.accept_rate * 100).toFixed(1)}% ({row.n_accepts})
                          </td>
                          <td className="py-2 pr-3">
                            {(row.completion_rate * 100).toFixed(1)}% ({row.n_completes})
                          </td>
                          <td className="py-2">{fmtMs(row.time_to_accept_ms_p50)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </ChartCard>
          ) : null}
        </div>
      )}
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-hair bg-panel/60 p-4">
      <h2 className="font-display text-base text-mist">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-hair/80 bg-soft/40 px-3 py-2">
      <dt className="text-[11px] uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-1 font-display text-mist">{value}</dd>
    </div>
  );
}

function fmtMs(value: number | null): string {
  return value == null ? '—' : `${value} ms`;
}
