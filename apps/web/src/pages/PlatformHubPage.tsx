import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Calendar, Inbox, Package, Stethoscope, Users } from 'lucide-react';
import type { CareRequest } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { useCurrentCareRelationship } from '../auth/useCurrentCareRelationship';
import { useCaregiverProfile } from '../auth/useCaregiverProfile';
import { usePatientProfile } from '../auth/usePatientProfile';
import { ActiveCareLinkCard } from '../components/ActiveCareLinkCard';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { PageHeader } from '../components/ui/PageHeader';
import { StatCard } from '../components/ui/StatCard';
import { useLocale } from '../i18n/LocaleProvider';

function Shortcut({ to, title, desc }: { to: string; title: string; desc: string }) {
  return (
    <Link
      to={to}
      className="block rounded-2xl border border-hair bg-panel p-4 shadow-[var(--cp-shadow-soft)] transition hover:border-cyan/40"
    >
      <p className="font-display text-base font-semibold text-mist">{title}</p>
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
  const [caregiverCount, setCaregiverCount] = useState<number | null>(null);
  const [requestCount, setRequestCount] = useState<number | null>(null);
  const [packageCount, setPackageCount] = useState<number | null>(null);
  const [requests, setRequests] = useState<CareRequest[]>([]);
  const [adminUsers, setAdminUsers] = useState<number | null>(null);
  const [activeLinks, setActiveLinks] = useState<number | null>(null);

  const firstName = user?.email?.split('@')[0] ?? 'there';

  useEffect(() => {
    let cancelled = false;
    const tasks: Promise<void>[] = [
      api
        .caregivers({ page_size: 1 })
        .then((res) => {
          if (!cancelled) setCaregiverCount(res.count);
        })
        .catch(() => {
          if (!cancelled) setCaregiverCount(null);
        }),
      api
        .listCareRequests(1)
        .then((res) => {
          if (!cancelled) {
            setRequestCount(res.count);
            setRequests(res.results.slice(0, 6));
          }
        })
        .catch(() => {
          if (!cancelled) {
            setRequestCount(null);
            setRequests([]);
          }
        }),
      api
        .listCarePackages()
        .then((pkgs) => {
          if (!cancelled) setPackageCount(pkgs.length);
        })
        .catch(() => {
          if (!cancelled) setPackageCount(null);
        }),
    ];
    if (user?.role === 'admin' || user?.role === 'auditor') {
      tasks.push(
        api
          .getAdminAnalytics()
          .then((a) => {
            if (cancelled) return;
            const users = a.roles.reduce((sum, row) => sum + row.count, 0);
            setAdminUsers(users);
            setActiveLinks(a.relationships.active);
          })
          .catch(() => {
            if (!cancelled) {
              setAdminUsers(null);
              setActiveLinks(null);
            }
          }),
      );
    }
    void Promise.all(tasks);
    return () => {
      cancelled = true;
    };
  }, [user?.role]);

  const fmt = (n: number | null) => (n == null ? '—' : String(n));

  return (
    <div>
      <PageHeader
        eyebrow={t('hub.eyebrow')}
        title={t('hub.welcome', { name: firstName })}
        subtitle={t('hub.subtitle')}
      />

      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={<Stethoscope size={20} />}
          title="Caregivers"
          value={fmt(caregiverCount)}
          subtitle="Directory matches available to browse"
          highlight
        />
        <StatCard
          icon={<Inbox size={20} />}
          title={user?.role === 'caregiver' ? 'Inbox' : 'Your requests'}
          value={fmt(requestCount)}
          subtitle="Care requests on this account"
        />
        <StatCard
          icon={<Package size={20} />}
          title="Packages"
          value={fmt(packageCount)}
          subtitle="Published care packages"
        />
        {(user?.role === 'admin' || user?.role === 'auditor') && (
          <StatCard
            icon={<Users size={20} />}
            title="Users"
            value={fmt(adminUsers)}
            subtitle={
              activeLinks != null ? `${activeLinks} active care links` : 'Platform accounts'
            }
          />
        )}
        {user?.role !== 'admin' && user?.role !== 'auditor' && (
          <StatCard
            icon={<Calendar size={20} />}
            title="Profile"
            value={`${user?.role === 'caregiver' ? caregiver.completionPercent : patient.completionPercent}%`}
            subtitle="Onboarding completeness"
          />
        )}
      </div>

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
        <Card className="mt-6">
          <p className="font-display text-lg font-semibold text-mist">{t('hub.noLinkTitle')}</p>
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
        </Card>
      )}

      {requests.length > 0 && (
        <Card className="mt-6 overflow-x-auto p-0">
          <div className="flex items-center justify-between border-b border-hair px-5 py-4">
            <h2 className="font-display text-lg font-semibold text-mist">Recent requests</h2>
            <Link to="/requests" className="text-sm font-semibold text-cyan hover:underline">
              View all
            </Link>
          </div>
          <table className="w-full min-w-[32rem] text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-5 py-3 font-semibold">ID</th>
                <th className="px-5 py-3 font-semibold">Caregiver</th>
                <th className="px-5 py-3 font-semibold">Status</th>
                <th className="px-5 py-3 font-semibold">Patient</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((row) => (
                <tr key={row.id} className="border-t border-hair">
                  <td className="px-5 py-3 font-mono text-xs text-muted">#{row.id}</td>
                  <td className="px-5 py-3 text-mist">{row.caregiver_name}</td>
                  <td className="px-5 py-3 capitalize text-cyan">{row.status}</td>
                  <td className="px-5 py-3 text-muted">{row.patient_email}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <section className="mt-8">
        <h2 className="font-display text-lg font-semibold text-mist">{t('hub.quickActions')}</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Shortcut to="/messages" title={t('hub.messagesTitle')} desc={t('hub.messagesDesc')} />
          <Shortcut
            to="/requests"
            title={user?.role === 'caregiver' ? t('hub.inboxTitle') : t('hub.requestsTitle')}
            desc={t('hub.requestsDesc')}
          />
          {(user?.role === 'patient' || user?.role === 'caregiver') && (
            <Shortcut to="/schedule" title={t('hub.scheduleTitle')} desc={t('hub.scheduleDesc')} />
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
            <Shortcut to="/admin/audit" title={t('hub.auditTitle')} desc={t('hub.auditDesc')} />
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
