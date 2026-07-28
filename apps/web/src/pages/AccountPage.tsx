import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useCaregiverProfile } from '../auth/useCaregiverProfile';
import { usePatientProfile } from '../auth/usePatientProfile';
import { Button } from '../components/ui/Button';
import { PageHeader } from '../components/ui/PageHeader';

function SettingsLink({ to, title, desc }: { to: string; title: string; desc: string }) {
  return (
    <Link
      to={to}
      className="rounded-2xl border border-hair bg-panel/50 p-4 transition hover:border-cyan/40"
    >
      <p className="font-display text-base text-mist">{title}</p>
      <p className="mt-1 text-sm text-muted">{desc}</p>
    </Link>
  );
}

export function AccountPage() {
  const { user } = useAuth();
  const patient = usePatientProfile();
  const caregiver = useCaregiverProfile();
  const profilePath = user?.role === 'caregiver' ? '/caregiver-onboarding' : '/onboarding';

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        eyebrow="Account"
        title="Profile and settings"
        subtitle="Manage identity, profile completion, and notification preferences."
      />

      <section className="mt-6 rounded-2xl border border-hair bg-panel/50 p-5">
        <p className="font-display text-lg text-mist">Identity</p>
        <p className="mt-2 text-sm text-muted">
          Signed in as <span className="text-mist">{user?.email ?? 'unknown'}</span>
        </p>
        <p className="mt-1 text-sm text-muted">
          Role: <span className="text-mist">{user?.role ?? 'unknown'}</span>
        </p>
      </section>

      <section className="mt-6 rounded-2xl border border-hair bg-panel/50 p-5">
        <p className="font-display text-lg text-mist">Profile completion</p>
        {user?.role === 'patient' && (
          <div className="mt-2 text-sm text-muted">
            <p>Completion: {patient.completionPercent}%</p>
            <p className="mt-1">Care request ready: {patient.canRequestCare ? 'Yes' : 'No'}</p>
            <Link to={profilePath} className="mt-3 inline-block">
              <Button tone="ghost" className="min-h-9 px-3 py-1.5 text-xs">
                Update patient profile
              </Button>
            </Link>
          </div>
        )}
        {user?.role === 'caregiver' && (
          <div className="mt-2 text-sm text-muted">
            <p>Completion: {caregiver.completionPercent}%</p>
            <p className="mt-1">Match eligible: {caregiver.isMatchEligible ? 'Yes' : 'No'}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Link to={profilePath}>
                <Button tone="ghost" className="min-h-9 px-3 py-1.5 text-xs">
                  Update caregiver profile
                </Button>
              </Link>
              <Link to="/presence">
                <Button tone="ghost" className="min-h-9 px-3 py-1.5 text-xs">
                  Update availability
                </Button>
              </Link>
            </div>
          </div>
        )}
        {user?.role === 'admin' && (
          <div className="mt-3">
            <Link to="/leads">
              <Button tone="ghost" className="min-h-9 px-3 py-1.5 text-xs">
                Open leads inbox
              </Button>
            </Link>
          </div>
        )}
      </section>

      <section className="mt-6 grid gap-3 sm:grid-cols-2">
        <SettingsLink
          to="/settings/notifications"
          title="Notification settings"
          desc="Email and push preferences for care events."
        />
        <SettingsLink
          to="/messages"
          title="Messaging"
          desc="Open care chat with your linked partner."
        />
        <SettingsLink
          to="/records"
          title="Medical records"
          desc="Manage notes and attachments."
        />
        <SettingsLink
          to="/requests"
          title="Care requests"
          desc="Track request states and checkout."
        />
      </section>
    </div>
  );
}
