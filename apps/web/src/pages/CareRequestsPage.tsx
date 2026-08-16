import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { CareRequest } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { PageHeader } from '../components/ui/PageHeader';
import { Button } from '../components/ui/Button';

const STATUS_LABEL: Record<string, string> = {
  pending: 'Pending',
  accepted: 'Accepted',
  rejected: 'Rejected',
  cancelled: 'Cancelled',
  expired: 'Expired',
  draft: 'Draft',
};

export function CareRequestsPage() {
  const { user } = useAuth();
  const [rows, setRows] = useState<CareRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [rejectId, setRejectId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [endRelId, setEndRelId] = useState<number | null>(null);
  const [endReason, setEndReason] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .listCareRequests()
      .then((data) => setRows(data.results))
      .catch((err) => {
        setRows([]);
        setError(err instanceof Error ? err.message : 'Could not load requests.');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (user?.role === 'patient' || user?.role === 'caregiver') {
      load();
    } else {
      setLoading(false);
    }
  }, [user?.role, load]);

  async function onAccept(id: number) {
    setBusyId(id);
    try {
      const updated = await api.acceptCareRequest(id);
      setRows((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not accept request.');
    } finally {
      setBusyId(null);
    }
  }

  async function onReject(id: number) {
    setBusyId(id);
    try {
      const updated = await api.rejectCareRequest(id, rejectReason.trim() || undefined);
      setRows((prev) => prev.map((r) => (r.id === id ? updated : r)));
      setRejectId(null);
      setRejectReason('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not reject request.');
    } finally {
      setBusyId(null);
    }
  }

  async function onEndRelationship(relationshipId: number) {
    setBusyId(relationshipId);
    try {
      await api.endCareRelationship(relationshipId, endReason.trim() || undefined);
      setEndRelId(null);
      setEndReason('');
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not end care relationship.');
    } finally {
      setBusyId(null);
    }
  }

  async function onCancel(id: number) {
    setBusyId(id);
    try {
      const updated = await api.cancelCareRequest(id);
      setRows((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not cancel request.');
    } finally {
      setBusyId(null);
    }
  }

  const isPatient = user?.role === 'patient';
  const isCaregiver = user?.role === 'caregiver';

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col">
      <PageHeader
        eyebrow={isCaregiver ? 'Inbox' : 'Care requests'}
        title={isCaregiver ? 'Patient requests' : 'Your requests'}
        subtitle={
          isCaregiver
            ? 'Accept or decline requests from families.'
            : 'Track requests and finish LKR checkout when accepted.'
        }
        actions={
          isPatient ? (
            <Link to="/caregivers">
              <Button tone="ghost" className="min-h-9 px-3 py-1.5 text-xs">
                Browse caregivers
              </Button>
            </Link>
          ) : undefined
        }
      />

      {!isPatient && !isCaregiver && (
        <p className="mt-8 text-sm text-muted">
          Only patients and caregivers can view care requests.
        </p>
      )}

      {loading && <p className="mt-8 text-sm text-muted">Loading…</p>}
      {error && (
        <p className="mt-8 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
          {error}
        </p>
      )}

      {!loading && (isPatient || isCaregiver) && rows.length === 0 && (
        <div className="mt-8 rounded-2xl border border-hair bg-panel shadow-[var(--cp-shadow-soft)] p-5">
          <p className="text-sm text-muted">
            {isCaregiver
              ? 'Inbox empty. Requests appear when families send one from Serah matches or caregiver profiles.'
              : 'No requests yet. Browse caregivers across Sri Lanka or ask Serah in Sinhala, Tamil, or English.'}
          </p>
          {isPatient && (
            <div className="mt-4 flex flex-wrap gap-2">
              <Link to="/caregivers">
                <Button>Browse caregivers</Button>
              </Link>
              <Link to="/app">
                <Button tone="ghost">Ask Serah</Button>
              </Link>
            </div>
          )}
        </div>
      )}

      <ul className="mt-8 space-y-3">
        {rows.map((row) => (
          <li
            key={row.id}
            className="rounded-2xl border border-hair bg-panel/70 p-5 backdrop-blur-md"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-display text-lg text-mist">
                  {isCaregiver ? row.patient_email : row.caregiver_name}
                </p>
                <p className="mt-1 text-xs text-muted">
                  {STATUS_LABEL[row.status] || row.status}
                  {row.expires_at && row.status === 'pending'
                    ? ` · expires ${new Date(row.expires_at).toLocaleString()}`
                    : ''}
                </p>
              </div>
              {isPatient && row.status === 'pending' && (
                <button
                  type="button"
                  disabled={busyId === row.id}
                  onClick={() => void onCancel(row.id)}
                  className="rounded-lg border border-hair px-3 py-1 text-xs text-muted hover:border-rose hover:text-rose disabled:opacity-50"
                >
                  Cancel
                </button>
              )}
            </div>
            {row.message && <p className="mt-3 text-sm text-mist/90">{row.message}</p>}
            {row.match_snapshot?.score != null && (
              <p className="mt-2 text-xs text-cyan">
                Match score {Math.round(Number(row.match_snapshot.score) * 100)}%
                {row.match_snapshot.rank != null ? ` · rank #${row.match_snapshot.rank}` : ''}
              </p>
            )}
            {isCaregiver && row.status === 'pending' && rejectId !== row.id && (
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  disabled={busyId === row.id}
                  onClick={() => void onAccept(row.id)}
                  className="rounded-lg border border-mint/50 px-3 py-1.5 text-xs text-mint transition hover:bg-mint/10 disabled:opacity-50"
                >
                  Accept
                </button>
                <button
                  type="button"
                  disabled={busyId === row.id}
                  onClick={() => {
                    setRejectId(row.id);
                    setRejectReason('');
                  }}
                  className="rounded-lg border border-rose/40 px-3 py-1.5 text-xs text-rose transition hover:bg-rose/10 disabled:opacity-50"
                >
                  Reject
                </button>
              </div>
            )}
            {isCaregiver && rejectId === row.id && (
              <div className="mt-3 space-y-2 rounded-xl border border-rose/30 bg-rose/5 p-3">
                <input
                  className="w-full rounded-lg border border-hair bg-elevated px-3 py-2 text-sm text-mist outline-none"
                  placeholder="Optional reason for the patient"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={busyId === row.id}
                    onClick={() => void onReject(row.id)}
                    className="rounded-lg border border-rose/40 px-3 py-1.5 text-xs text-rose"
                  >
                    Confirm reject
                  </button>
                  <button
                    type="button"
                    onClick={() => setRejectId(null)}
                    className="rounded-lg border border-hair px-3 py-1.5 text-xs text-muted"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
            {row.relationship_id != null && row.relationship_status === 'pending_payment' && (
              <div className="mt-3 flex flex-col gap-2">
                {isPatient ? (
                  <>
                    <p className="text-xs text-amber">
                      Caregiver accepted — choose a package and pay to activate care.
                    </p>
                    <Link
                      to={`/requests/${row.id}/checkout`}
                      className="w-fit rounded-lg border border-mint/50 px-3 py-1.5 text-xs text-mint transition hover:bg-mint/10"
                    >
                      Complete payment
                    </Link>
                  </>
                ) : (
                  <p className="text-xs text-amber">
                    Waiting for the patient to complete payment before care activates.
                  </p>
                )}
              </div>
            )}
            {row.relationship_id != null &&
              row.relationship_status === 'active' &&
              endRelId !== row.relationship_id && (
                <div className="mt-3 flex flex-col gap-2">
                  <p className="text-xs text-mint">Active care link #{row.relationship_id}</p>
                  <button
                    type="button"
                    disabled={busyId === row.relationship_id}
                    onClick={() => {
                      setEndRelId(row.relationship_id!);
                      setEndReason('');
                    }}
                    className="w-fit rounded-lg border border-rose/40 px-3 py-1.5 text-xs text-rose transition hover:bg-rose/10 disabled:opacity-50"
                  >
                    End care
                  </button>
                </div>
              )}
            {row.relationship_id != null && endRelId === row.relationship_id && (
              <div className="mt-3 space-y-2 rounded-xl border border-rose/30 bg-rose/5 p-3">
                <input
                  className="w-full rounded-lg border border-hair bg-elevated px-3 py-2 text-sm text-mist outline-none"
                  placeholder="Optional reason for ending care"
                  value={endReason}
                  onChange={(e) => setEndReason(e.target.value)}
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={busyId === row.relationship_id}
                    onClick={() => void onEndRelationship(row.relationship_id!)}
                    className="rounded-lg border border-rose/40 px-3 py-1.5 text-xs text-rose"
                  >
                    Confirm end care
                  </button>
                  <button
                    type="button"
                    onClick={() => setEndRelId(null)}
                    className="rounded-lg border border-hair px-3 py-1.5 text-xs text-muted"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
            {row.relationship_id != null && row.relationship_status === 'ended' && (
              <p className="mt-3 text-xs text-muted">Care link ended · history retained</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
