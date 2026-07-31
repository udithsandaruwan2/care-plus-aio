import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useCurrentCareRelationship } from '../auth/useCurrentCareRelationship';
import { useCaregiverProfile } from '../auth/useCaregiverProfile';
import { usePatientProfile } from '../auth/usePatientProfile';
import { ActiveCareLinkCard } from '../components/ActiveCareLinkCard';
import { Button } from '../components/ui/Button';
import { PageHeader } from '../components/ui/PageHeader';
import { useLocale } from '../i18n/LocaleProvider';

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
  const { t } = useLocale();
  const care = useCurrentCareRelationship();
  const patient = usePatientProfile();
  const caregiver = useCaregiverProfile();

  const firstName = user?.email?.split('@')[0] ?? 'there';

  return (
    <div>
      <PageHeader
        eyebrow={t('hub.eyebrow')}
        title={t('hub.welcome', { name: firstName })}
        subtitle={t('hub.subtitle')}
      />

      {user?.role === 'patient' && !patient.canRequestCare && (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber/40 bg-amber/5 px-4 py-3">
          <p className="text-sm text-amber">
            {t('hub.patientProfileHint', { percent: patient.completionPercent })}
          </p>
          <Link to="/onboarding">
            <Button className="min-h-9 px-3 py-1.5 text-xs">{t('action.continueProfile')}</Button>
          </Link>
        </div>
      )}

      {user?.role === 'caregiver' && !caregiver.isMatchEligible && (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber/40 bg-amber/5 px-4 py-3">
          <p className="text-sm text-amber">
            {t('hub.caregiverProfileHint', { percent: caregiver.completionPercent })}
          </p>
          <Link to="/caregiver-onboarding">
            <Button className="min-h-9 px-3 py-1.5 text-xs">{t('action.continueProfile')}</Button>
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
          <p className="font-display text-lg text-mist">{t('hub.noLinkTitle')}</p>
          <p className="mt-1 text-sm text-muted">
            {user?.role === 'patient' ? t('hub.noLinkPatient') : t('hub.noLinkCaregiver')}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {user?.role === 'patient' && (
              <>
                <Link to="/caregivers">
                  <Button>{t('action.browseCaregivers')}</Button>
                </Link>
                <Link to="/app">
                  <Button tone="ghost">{t('action.askSerah')}</Button>
                </Link>
              </>
            )}
            {user?.role === 'caregiver' && (
              <Link to="/requests">
                <Button>{t('action.openInbox')}</Button>
              </Link>
            )}
          </div>
        </div>
      )}

      <section className="mt-8">
        <h2 className="font-display text-lg text-mist">{t('hub.quickActions')}</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Shortcut to="/messages" title={t('hub.messagesTitle')} desc={t('hub.messagesDesc')} />
          <Shortcut
            to="/requests"
            title={user?.role === 'caregiver' ? t('hub.inboxTitle') : t('hub.requestsTitle')}
            desc={t('hub.requestsDesc')}
          />
          {(user?.role === 'patient' || user?.role === 'caregiver') && (
            <Shortcut
              to="/schedule"
              title={t('hub.scheduleTitle')}
              desc={t('hub.scheduleDesc')}
            />
          )}
          <Shortcut to="/records" title={t('hub.recordsTitle')} desc={t('hub.recordsDesc')} />
          <Shortcut to="/account" title={t('hub.accountTitle')} desc={t('hub.accountDesc')} />
          <Shortcut to="/app" title={t('hub.serahTitle')} desc={t('hub.serahDesc')} />
          {(user?.role === 'admin' || user?.role === 'auditor') && (
            <Shortcut
              to="/users"
              title={t('hub.usersTitle')}
              desc={user.role === 'admin' ? t('hub.usersDescAdmin') : t('hub.usersDescAuditor')}
            />
          )}
          {(user?.role === 'admin' || user?.role === 'auditor') && (
            <Shortcut
              to="/admin/analytics"
              title={t('hub.analyticsTitle')}
              desc={t('hub.analyticsDesc')}
            />
          )}
          {(user?.role === 'admin' || user?.role === 'auditor') && (
            <Shortcut
              to="/admin/audit"
              title={t('hub.auditTitle')}
              desc={t('hub.auditDesc')}
            />
          )}
          {(user?.role === 'admin' || user?.role === 'auditor') && (
            <Shortcut
              to="/admin/catalog"
              title={t('hub.catalogTitle')}
              desc={t('hub.catalogDesc')}
            />
          )}
          {user?.role === 'admin' && (
            <Shortcut to="/leads" title={t('hub.leadsTitle')} desc={t('hub.leadsDesc')} />
          )}
          <Shortcut to="/catalog" title={t('hub.packagesTitle')} desc={t('hub.packagesDesc')} />
        </div>
      </section>
    </div>
  );
}
