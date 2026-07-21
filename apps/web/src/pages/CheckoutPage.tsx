import { FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import type { CarePackage, CatalogAddOn } from '@care-plus/api-client';
import { AtmosphereShell } from '../components/AtmosphereShell';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { formatLkr } from '../lib/formatLkr';

/** Select package + add-ons + days, create Order, go to pay (Step 32). */
export function CheckoutPage() {
  const { careRequestId } = useParams<{ careRequestId: string }>();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [packages, setPackages] = useState<CarePackage[]>([]);
  const [addons, setAddons] = useState<CatalogAddOn[]>([]);
  const [packageId, setPackageId] = useState<number | null>(null);
  const [addonIds, setAddonIds] = useState<number[]>([]);
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const requestId = Number(careRequestId);

  useEffect(() => {
    if (user?.role !== 'patient') {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    Promise.all([api.listCarePackages(), api.listCatalogAddOns()])
      .then(([pkgs, ads]) => {
        setPackages(pkgs);
        setAddons(ads);
        if (pkgs.length > 0) {
          setPackageId(pkgs[0].id);
          setDays(pkgs[0].default_days);
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Could not load catalog.');
      })
      .finally(() => setLoading(false));
  }, [user?.role]);

  function toggleAddon(id: number) {
    setAddonIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!packageId || !Number.isFinite(requestId)) return;
    setSubmitting(true);
    setError(null);
    try {
      const order = await api.createCheckout({
        care_request_id: requestId,
        package_id: packageId,
        addon_ids: addonIds,
        days,
      });
      navigate(`/orders/${order.id}/pay`, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create checkout order.');
    } finally {
      setSubmitting(false);
    }
  }

  const selectedPkg = packages.find((p) => p.id === packageId);
  const estimate =
    selectedPkg != null
      ? Number(selectedPkg.price_lkr) * days +
        addonIds.reduce((sum, id) => {
          const a = addons.find((x) => x.id === id);
          return sum + (a ? Number(a.price_lkr) : 0);
        }, 0)
      : 0;

  return (
    <AtmosphereShell>
      <main className="mx-auto flex min-h-full max-w-3xl flex-col px-6 py-10">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-display text-sm uppercase tracking-[0.2em] text-cyan">Checkout</p>
            <h1 className="mt-2 font-display text-3xl font-semibold text-mist">Choose care package</h1>
            <p className="mt-2 text-sm text-muted">
              Request #{Number.isFinite(requestId) ? requestId : '—'} · priced in LKR
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              to="/requests"
              className="rounded-lg border border-hair px-3 py-1.5 text-sm text-muted hover:border-cyan hover:text-cyan"
            >
              Requests
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

        {user?.role !== 'patient' && (
          <p className="mt-8 text-sm text-muted">Only patients can complete checkout.</p>
        )}

        {loading && <p className="mt-8 text-sm text-muted">Loading catalog…</p>}
        {error && (
          <p className="mt-8 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
            {error}
          </p>
        )}

        {user?.role === 'patient' && !loading && (
          <form onSubmit={(e) => void onSubmit(e)} className="mt-8 space-y-6">
            <section className="space-y-3">
              <h2 className="font-display text-lg text-mist">Package</h2>
              {packages.map((pkg) => (
                <label
                  key={pkg.id}
                  className={`flex cursor-pointer flex-wrap items-start justify-between gap-3 rounded-2xl border p-5 backdrop-blur-md transition ${
                    packageId === pkg.id
                      ? 'border-mint/50 bg-mint/5'
                      : 'border-hair bg-panel/70 hover:border-cyan/40'
                  }`}
                >
                  <div className="flex gap-3">
                    <input
                      type="radio"
                      name="package"
                      checked={packageId === pkg.id}
                      onChange={() => {
                        setPackageId(pkg.id);
                        setDays(pkg.default_days);
                      }}
                      className="mt-1"
                    />
                    <div>
                      <p className="font-display text-lg text-mist">{pkg.name}</p>
                      <p className="mt-1 text-xs uppercase tracking-wide text-muted">
                        {pkg.care_level} · {formatLkr(pkg.price_lkr)} / day
                      </p>
                      {pkg.description && (
                        <p className="mt-2 text-sm text-mist/90">{pkg.description}</p>
                      )}
                    </div>
                  </div>
                </label>
              ))}
            </section>

            <section className="space-y-3">
              <h2 className="font-display text-lg text-mist">Add-ons</h2>
              {addons.length === 0 && <p className="text-sm text-muted">No add-ons available.</p>}
              {addons.map((addon) => (
                <label
                  key={addon.id}
                  className={`flex cursor-pointer items-start justify-between gap-3 rounded-2xl border p-5 backdrop-blur-md ${
                    addonIds.includes(addon.id)
                      ? 'border-cyan/50 bg-cyan/5'
                      : 'border-hair bg-panel/70'
                  }`}
                >
                  <div className="flex gap-3">
                    <input
                      type="checkbox"
                      checked={addonIds.includes(addon.id)}
                      onChange={() => toggleAddon(addon.id)}
                      className="mt-1"
                    />
                    <div>
                      <p className="font-display text-mist">{addon.name}</p>
                      <p className="mt-1 text-xs uppercase tracking-wide text-muted">
                        {addon.category}
                      </p>
                    </div>
                  </div>
                  <p className="font-mono text-mint">{formatLkr(addon.price_lkr)}</p>
                </label>
              ))}
            </section>

            <label className="block">
              <span className="text-sm text-muted">Days of care</span>
              <input
                type="number"
                min={1}
                max={365}
                value={days}
                onChange={(e) => setDays(Math.max(1, Number(e.target.value) || 1))}
                className="mt-2 w-full rounded-xl border border-hair bg-panel/70 px-4 py-2.5 text-mist outline-none focus:border-cyan"
              />
            </label>

            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber/40 bg-amber/5 px-5 py-4">
              <p className="text-sm text-amber">Estimated total</p>
              <p className="font-mono text-lg text-mint">{formatLkr(estimate)}</p>
            </div>

            <button
              type="submit"
              disabled={submitting || packageId == null}
              className="rounded-lg border border-mint/50 px-4 py-2.5 text-sm text-mint transition hover:bg-mint/10 disabled:opacity-50"
            >
              {submitting ? 'Creating order…' : 'Continue to payment'}
            </button>
          </form>
        )}
      </main>
    </AtmosphereShell>
  );
}
