import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { CareRelationship } from '@care-plus/api-client';
import { api } from '../auth/api';
import { Button } from './ui/Button';
import { Input } from './ui/Input';

type Props = {
  relationship: CareRelationship;
  role: 'patient' | 'caregiver';
  onEnded: () => void;
};

export function ActiveCareLinkCard({ relationship, role, onEnded }: Props) {
  const partnerLabel =
    role === 'patient'
      ? relationship.caregiver_name
      : relationship.patient_display_name || relationship.patient_email;

  const started = relationship.started_at
    ? new Date(relationship.started_at).toLocaleDateString()
    : null;

  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onEnd() {
    setBusy(true);
    setError(null);
    try {
      await api.endCareRelationship(relationship.id, reason.trim() || undefined);
      setConfirming(false);
      setReason('');
      onEnded();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not end care.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-6 w-full rounded-2xl border border-mint/40 bg-mint/5 p-5 backdrop-blur-md">
      <p className="font-display text-xs uppercase tracking-[0.2em] text-mint">
        {role === 'patient' ? 'Your caregiver' : 'Your patient'}
      </p>
      <h2 className="mt-2 font-display text-xl text-mist">{partnerLabel}</h2>
      <p className="mt-1 text-xs text-muted">
        Active since {started ?? 'recently'} · link #{relationship.id}
      </p>

      {!confirming && (
        <div className="mt-4 flex flex-wrap gap-2">
          {role === 'patient' ? (
            <Link
              to={`/caregivers/${relationship.caregiver_id}`}
              className="rounded-lg border border-cyan/40 px-3 py-1.5 text-xs text-cyan transition hover:bg-cyan/10"
            >
              Profile
            </Link>
          ) : (
            <Link
              to="/requests"
              className="rounded-lg border border-cyan/40 px-3 py-1.5 text-xs text-cyan transition hover:bg-cyan/10"
            >
              Requests
            </Link>
          )}
          <Link
            to="/messages"
            className="rounded-lg border border-cyan/40 px-3 py-1.5 text-xs text-cyan transition hover:bg-cyan/10"
          >
            Messages
          </Link>
          <Link
            to="/records"
            className="rounded-lg border border-hair px-3 py-1.5 text-xs text-muted transition hover:border-violet hover:text-violet"
          >
            Care records
          </Link>
          <button
            type="button"
            onClick={() => setConfirming(true)}
            className="rounded-lg border border-rose/40 px-3 py-1.5 text-xs text-rose transition hover:bg-rose/10"
          >
            End care
          </button>
        </div>
      )}

      {confirming && (
        <div className="mt-4 space-y-3 rounded-xl border border-rose/30 bg-rose/5 p-4">
          <p className="text-sm text-mist">End this care relationship?</p>
          <Input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Optional reason"
          />
          {error && <p className="text-xs text-rose">{error}</p>}
          <div className="flex flex-wrap gap-2">
            <Button
              tone="danger"
              className="min-h-9 px-3 py-1.5 text-xs"
              disabled={busy}
              onClick={() => void onEnd()}
            >
              {busy ? 'Ending…' : 'Confirm end care'}
            </Button>
            <Button
              tone="ghost"
              className="min-h-9 px-3 py-1.5 text-xs"
              disabled={busy}
              onClick={() => {
                setConfirming(false);
                setError(null);
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
