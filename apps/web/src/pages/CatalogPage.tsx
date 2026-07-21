import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { CarePackage, CatalogAddOn } from '@care-plus/api-client';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { formatLkr } from '../lib/formatLkr';

/** Browse LKR care packages and add-ons (Step 29). */
export function CatalogPage() {
  const { user, logout } = useAuth();
  const [packages, setPackages] = useState<CarePackage[]>([]);
  const [addons, setAddons] = useState<CatalogAddOn[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([api.listCarePackages(), api.listCatalogAddOns()])
      .then(([pkgs, ads]) => {
        setPackages(pkgs);
        setAddons(ads);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Could not load catalog.');
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <AtmosphereShell>
      <main className="mx-auto flex min-h-full max-w-3xl flex-col px-6 py-10">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-display text-sm uppercase tracking-[0.2em] text-cyan">Catalog</p>
            <h1 className="mt-2 font-display text-3xl font-semibold text-mist">Care packages</h1>
            <p className="mt-2 text-sm text-muted">
              LKR packages and add-ons. After a caregiver accepts your request, checkout from Care
              requests.
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              to="/"
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted hover:border-cyan hover:text-cyan"
            >
              Home
            </Link>
            {user && (
              <button
                type="button"
                onClick={logout}
                className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted hover:border-rose hover:text-rose"
              >
                Sign out
              </button>
            )}
          </div>
        </div>

        {loading && <p className="mt-8 text-sm text-muted">Loading…</p>}
        {error && (
          <p className="mt-8 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
            {error}
          </p>
        )}

        <section className="mt-8 space-y-3">
          <h2 className="font-display text-lg text-mist">Packages</h2>
          {packages.map((pkg) => (
            <article
              key={pkg.id}
              className="rounded-2xl border border-hair bg-panel/70 p-5 backdrop-blur-md"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-display text-lg text-mist">{pkg.name}</p>
                  <p className="mt-1 text-xs uppercase tracking-wide text-muted">
                    {pkg.care_level} · {pkg.default_days} days default
                  </p>
                </div>
                <p className="font-mono text-mint">{formatLkr(pkg.price_lkr)}</p>
              </div>
              {pkg.description && (
                <p className="mt-3 text-sm text-mist/90">{pkg.description}</p>
              )}
            </article>
          ))}
        </section>

        <section className="mt-10 space-y-3">
          <h2 className="font-display text-lg text-mist">Add-ons</h2>
          {addons.map((addon) => (
            <article
              key={addon.id}
              className="rounded-2xl border border-hair bg-panel/70 p-5 backdrop-blur-md"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-display text-lg text-mist">{addon.name}</p>
                  <p className="mt-1 text-xs uppercase tracking-wide text-muted">{addon.category}</p>
                </div>
                <p className="font-mono text-mint">{formatLkr(addon.price_lkr)}</p>
              </div>
              {addon.description && (
                <p className="mt-3 text-sm text-mist/90">{addon.description}</p>
              )}
            </article>
          ))}
        </section>
      </main>
    </AtmosphereShell>
  );
}
