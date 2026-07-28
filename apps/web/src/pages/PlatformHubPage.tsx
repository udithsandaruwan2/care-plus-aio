import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useCurrentCareRelationship } from '../auth/useCurrentCareRelationship';
import { useCaregiverProfile } from '../auth/useCaregiverProfile';
import { usePatientProfile } from '../auth/usePatientProfile';
import { ActiveCareLinkCard } from '../components/ActiveCareLinkCard';
import { Button } from '../components/ui/Button';
import { PageHeader } from '../components/ui/PageHeader';

function Shortcut({ to, title, desc }: { to: string; title: string; desc: string }) {
  return (
    <Link
      to={to}
      className="block rounded-2xl border border-hair bg-panel/50 p-4 transition hover:border-cyan/40"
    >
      <p className="font-display text-base text-mist">{title}</p>
      <p className="mt-1 text-sm text-muted">{desc}</p>
    </Link>
  );
}

export function PlatformHubPage() {
  const { user } = useAuth();
  const care = useCurrentCareRelationship();
  const patient = usePatientProfile();
  const caregiver = useCaregiverProfile();

  const firstName = user?.email?.split('@')[0] ?? 'there';

  return (
    <div>
      <PageHeader
        eyebrow="Home"
        title={`Welcome, ${firstName}`}
        subtitle="Manage care relationships, messages, records, and requests from one place."
      />

      {user?.role === 'patient' && !patient.canRequestCare && (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber/40 bg-amber/5 px-4 py-3">
          <p className="text-sm text-amber">
            Complete your patient profile ({patient.completionPercent}%) to request care.
          </p>
          <Link to="/onboarding">
            <Button className="min-h-9 px-3 py-1.5 text-xs">Continue profile</Button>
          </Link>
        </div>
      )}

      {user?.role === 'caregiver' && !caregiver.isMatchEligible && (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber/40 bg-amber/5 px-4 py-3">
          <p className="text-sm text-amber">
            Complete your caregiver profile ({caregiver.completionPercent}%) to appear in matching.
          </p>
          <Link to="/caregiver-onboarding">
            <Button className="min-h-9 px-3 py-1.5 text-xs">Continue profile</Button>
          </Link>
        </div>
      )}

      {care.relationship && (user?.role === 'patient' || user?.role === 'caregiver') && (
        <ActiveCareLinkCard
          relationship={care.relationship}
          role={user.role}
          onEnded={() => void care.refresh()}
        />
      )}

      {!care.loading && !care.relationship && (
        <div className="mt-6 rounded-2xl border border-hair bg-panel/50 p-5">
          <p className="font-display text-lg text-mist">No active care link yet</p>
          <p className="mt-1 text-sm text-muted">
            {user?.role === 'patient'
              ? 'Browse caregivers or ask Serah to find a match, then send a request.'
              : 'When a patient request is accepted and checkout completes, your care link appears here.'}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {user?.role === 'patient' && (
              <>
                <Link to="/caregivers">
                  <Button>Browse caregivers</Button>
                </Link>
                <Link to="/app">
                  <Button tone="ghost">Ask Serah</Button>
                </Link>
              </>
            )}
            {user?.role === 'caregiver' && (
              <Link to="/requests">
                <Button>Open inbox</Button>
              </Link>
            )}
          </div>
        </div>
      )}

      <section className="mt-8">
        <h2 className="font-display text-lg text-mist">Quick actions</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Shortcut to="/messages" title="Messages" desc="Chat with your care partner in real time." />
          <Shortcut
            to="/requests"
            title={user?.role === 'caregiver' ? 'Inbox' : 'Care requests'}
            desc="Track pending, accepted, and completed requests."
          />
          <Shortcut to="/records" title="Medical records" desc="Notes and attachments for active care." />
          <Shortcut to="/account" title="Account" desc="Profile completion and notification settings." />
          <Shortcut to="/app" title="Serah assistant" desc="Voice-guided matching in your language." />
          <Shortcut to="/catalog" title="Packages" desc="Review LKR care packages and add-ons." />
        </div>
      </section>
    </div>
  );
}
