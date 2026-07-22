import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { NotificationEventPreference } from '@care-plus/api-client';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';

const CATEGORY_LABEL: Record<string, string> = {
  security: 'Security (always on)',
  transactional: 'Care & account updates',
  marketing: 'Marketing',
};

function groupByCategory(events: NotificationEventPreference[]) {
  const groups: Record<string, NotificationEventPreference[]> = {};
  for (const event of events) {
    const cat = event.category;
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(event);
  }
  return groups;
}

export function NotificationPreferencesPage() {
  const { user, logout } = useAuth();
  const [events, setEvents] = useState<NotificationEventPreference[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return api
      .getNotificationPreferences()
      .then((data) => setEvents(data.events))
      .catch((err) => {
        setEvents([]);
        setError(err instanceof Error ? err.message : 'Could not load preferences.');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onToggle(
    eventKey: string,
    channel: 'email' | 'push',
    value: boolean,
    locked: boolean,
  ) {
    if (locked) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const data = await api.updateNotificationPreferences({ [channel]: { [eventKey]: value } });
      setEvents(data.events);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save preference.');
    } finally {
      setSaving(false);
    }
  }

  const grouped = groupByCategory(events);
  const categoryOrder = ['security', 'transactional', 'marketing'];

  return (
    <AtmosphereShell>
      <main className="mx-auto flex min-h-full max-w-3xl flex-col px-6 py-10">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-display text-sm uppercase tracking-[0.2em] text-amber">Settings</p>
            <h1 className="mt-2 font-display text-3xl font-semibold text-mist">
              Notification preferences
            </h1>
            <p className="mt-2 text-sm text-muted">
              Choose email and push alerts per event. Security alerts cannot be turned off.
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              to="/"
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted hover:border-cyan hover:text-cyan"
            >
              Neural Core
            </Link>
            <button
              type="button"
              onClick={logout}
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted hover:border-rose hover:text-rose"
            >
              Sign out
            </button>
          </div>
        </div>

        {user && (
          <p className="mt-4 text-xs text-muted">
            Signed in as <span className="text-mist">{user.email}</span>
          </p>
        )}

        {error && (
          <p className="mt-6 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
            {error}
          </p>
        )}
        {saved && !error && (
          <p className="mt-6 rounded-xl border border-mint/40 bg-mint/5 px-4 py-3 text-sm text-mint">
            Preferences saved.
          </p>
        )}

        {loading && <p className="mt-8 text-sm text-muted">Loading…</p>}

        {!loading &&
          categoryOrder.map((category) => {
            const rows = grouped[category];
            if (!rows?.length) return null;
            return (
              <section key={category} className="mt-8">
                <h2 className="font-display text-lg text-mist">{CATEGORY_LABEL[category]}</h2>
                <ul className="mt-3 space-y-3">
                  {rows.map((event) => (
                    <li
                      key={event.key}
                      className="rounded-2xl border border-hair bg-panel/70 p-5 backdrop-blur-md"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div className="min-w-0 flex-1">
                          <p className="font-display text-mist">{event.label}</p>
                          <p className="mt-1 text-xs text-muted">{event.description}</p>
                        </div>
                        <div className="flex flex-col gap-2 text-sm">
                          <label className="flex items-center gap-2 text-muted">
                            <input
                              type="checkbox"
                              checked={event.email}
                              disabled={event.locked || saving}
                              onChange={(e) =>
                                void onToggle(event.key, 'email', e.target.checked, event.locked)
                              }
                            />
                            Email
                          </label>
                          <label className="flex items-center gap-2 text-muted">
                            <input
                              type="checkbox"
                              checked={event.push}
                              disabled={event.locked || saving}
                              onChange={(e) =>
                                void onToggle(event.key, 'push', e.target.checked, event.locked)
                              }
                            />
                            Push
                          </label>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
      </main>
    </AtmosphereShell>
  );
}
