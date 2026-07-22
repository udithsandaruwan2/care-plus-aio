import { Link } from 'react-router-dom';
import type { CareRelationship } from '@care-plus/api-client';
import { api } from '../auth/api';

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

  async function onEnd() {
    const reason = window.prompt('Optional reason for ending care:') ?? '';
    if (reason === null) return;
    try {
      await api.endCareRelationship(relationship.id, reason.trim() || undefined);
      onEnded();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Could not end care.');
    }
  }

  return (
    <section className="mt-6 w-full max-w-md rounded-2xl border border-mint/40 bg-mint/5 p-5 backdrop-blur-md">
      <p className="font-display text-xs uppercase tracking-[0.2em] text-mint">
        {role === 'patient' ? 'Your caregiver' : 'Your patient'}
      </p>
      <h2 className="mt-2 font-display text-xl text-mist">{partnerLabel}</h2>
      <p className="mt-1 text-xs text-muted">
        Active since {started ?? 'recently'} · link #{relationship.id}
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        {role === 'patient' ? (
          <Link
            to={`/caregivers/${relationship.caregiver_id}`}
            className="rounded-lg border border-cyan/40 px-3 py-1.5 text-xs text-cyan transition hover:bg-cyan/10"
          >
            Message / profile
          </Link>
        ) : (
          <Link
            to="/requests"
            className="rounded-lg border border-cyan/40 px-3 py-1.5 text-xs text-cyan transition hover:bg-cyan/10"
          >
            Message / requests
          </Link>
        )}
        <Link
          to="/records"
          className="rounded-lg border border-hair px-3 py-1.5 text-xs text-muted transition hover:border-violet hover:text-violet"
        >
          Care records
        </Link>
        <button
          type="button"
          onClick={() => void onEnd()}
          className="rounded-lg border border-rose/40 px-3 py-1.5 text-xs text-rose transition hover:bg-rose/10"
        >
          End care
        </button>
      </div>
    </section>
  );
}
