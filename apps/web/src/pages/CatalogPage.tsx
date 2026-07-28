import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { CarePackage, CatalogAddOn } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { BackLink } from '../components/ui/BackLink';
import { Button } from '../components/ui/Button';
import { PageHeader } from '../components/ui/PageHeader';
import { formatLkr } from '../lib/formatLkr';

export function CatalogPage() {
  const { user } = useAuth();
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
    <div>
      <BackLink to="/">Home</BackLink>
      <div className="mt-4">
        <PageHeader
          eyebrow="Packages"
          title="Care packages"
          subtitle="Transparent LKR packages and add-ons. After a caregiver accepts your request, checkout from Care requests."
          actions={
            user ? (
              <Link to="/requests">
                <Button tone="ghost">Care requests</Button>
              </Link>
            ) : (
              <Link to="/register">
                <Button tone="ghost">Get started</Button>
              </Link>
            )
          }
        />
      </div>

      {loading && <p className="mt-8 text-sm text-muted">Loading…</p>}
      {error && (
        <p className="mt-8 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
          {error}
        </p>
      )}

      <section className="mt-10 space-y-4">
        <h2 className="font-display text-lg text-mist">Packages</h2>
        {packages.map((pkg) => (
          <article key={pkg.id} className="border-b border-hair/70 py-4 last:border-0">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-display text-lg text-mist">{pkg.name}</p>
                <p className="mt-1 text-xs uppercase tracking-wide text-muted">
                  {pkg.care_level} · {pkg.default_days} days default
                </p>
              </div>
              <p className="text-mint">{formatLkr(pkg.price_lkr)}</p>
            </div>
            {pkg.description && <p className="mt-3 text-sm text-mist/90">{pkg.description}</p>}
          </article>
        ))}
      </section>

      <section className="mt-12 space-y-4">
        <h2 className="font-display text-lg text-mist">Add-ons</h2>
        {addons.map((addon) => (
          <article key={addon.id} className="border-b border-hair/70 py-4 last:border-0">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-display text-lg text-mist">{addon.name}</p>
                <p className="mt-1 text-xs uppercase tracking-wide text-muted">{addon.category}</p>
              </div>
              <p className="text-mint">{formatLkr(addon.price_lkr)}</p>
            </div>
            {addon.description && (
              <p className="mt-3 text-sm text-mist/90">{addon.description}</p>
            )}
          </article>
        ))}
      </section>
    </div>
  );
}
