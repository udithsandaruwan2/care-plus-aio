import { FormEvent, useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { AdminConditionTerm, CarePackage, CatalogAddOn } from '@care-plus/api-client';
import { api } from '../auth/api';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { PageHeader } from '../components/ui/PageHeader';

type Tab = 'conditions' | 'packages' | 'addons';

/** Admin/auditor CRUD for vocab + catalog (Step 55). */
export function AdminCatalogPage() {
  const { user } = useAuth();
  const canWrite = user?.role === 'admin';
  const canRead = user?.role === 'admin' || user?.role === 'auditor';
  const [tab, setTab] = useState<Tab>('conditions');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [conditions, setConditions] = useState<AdminConditionTerm[]>([]);
  const [packages, setPackages] = useState<CarePackage[]>([]);
  const [addons, setAddons] = useState<CatalogAddOn[]>([]);

  const [condSlug, setCondSlug] = useState('');
  const [condName, setCondName] = useState('');
  const [pkgSlug, setPkgSlug] = useState('');
  const [pkgName, setPkgName] = useState('');
  const [pkgLevel, setPkgLevel] = useState<'basic' | 'intermediate' | 'advanced'>('basic');
  const [pkgPrice, setPkgPrice] = useState('15000');
  const [addonSlug, setAddonSlug] = useState('');
  const [addonName, setAddonName] = useState('');
  const [addonCategory, setAddonCategory] = useState<
    'hospital' | 'food' | 'transport' | 'supplies' | 'other'
  >('other');
  const [addonPrice, setAddonPrice] = useState('1000');

  const load = useCallback(async () => {
    setError(null);
    try {
      if (tab === 'conditions') {
        const data = await api.listAdminConditions();
        setConditions(data.results);
      } else if (tab === 'packages') {
        setPackages(await api.listAdminPackages());
      } else {
        setAddons(await api.listAdminAddOns());
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load admin catalog.');
    }
  }, [tab]);

  useEffect(() => {
    if (canRead) void load();
  }, [canRead, load]);

  async function onCreateCondition(e: FormEvent) {
    e.preventDefault();
    if (!canWrite || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.createAdminCondition({
        slug: condSlug.trim(),
        canonical_en: condName.trim(),
        synonyms: {},
        active: true,
        version: 1,
      });
      setCondSlug('');
      setCondName('');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Create failed.');
    } finally {
      setBusy(false);
    }
  }

  async function onToggleCondition(row: AdminConditionTerm) {
    if (!canWrite || busy) return;
    setBusy(true);
    try {
      await api.updateAdminCondition(row.slug, { active: !row.active });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed.');
    } finally {
      setBusy(false);
    }
  }

  async function onDeleteCondition(slug: string) {
    if (!canWrite || busy) return;
    setBusy(true);
    try {
      await api.deleteAdminCondition(slug);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed.');
    } finally {
      setBusy(false);
    }
  }

  async function onCreatePackage(e: FormEvent) {
    e.preventDefault();
    if (!canWrite || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.createAdminPackage({
        slug: pkgSlug.trim(),
        name: pkgName.trim(),
        description: '',
        care_level: pkgLevel,
        price_lkr: pkgPrice,
        default_days: 7,
        is_active: true,
        sort_order: 0,
      });
      setPkgSlug('');
      setPkgName('');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Create failed.');
    } finally {
      setBusy(false);
    }
  }

  async function onTogglePackage(row: CarePackage) {
    if (!canWrite || busy) return;
    setBusy(true);
    try {
      await api.updateAdminPackage(row.id, { is_active: !row.is_active });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed.');
    } finally {
      setBusy(false);
    }
  }

  async function onDeletePackage(id: number) {
    if (!canWrite || busy) return;
    setBusy(true);
    try {
      await api.deleteAdminPackage(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed.');
    } finally {
      setBusy(false);
    }
  }

  async function onCreateAddOn(e: FormEvent) {
    e.preventDefault();
    if (!canWrite || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.createAdminAddOn({
        slug: addonSlug.trim(),
        name: addonName.trim(),
        description: '',
        category: addonCategory,
        price_lkr: addonPrice,
        is_active: true,
        sort_order: 0,
      });
      setAddonSlug('');
      setAddonName('');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Create failed.');
    } finally {
      setBusy(false);
    }
  }

  async function onToggleAddOn(row: CatalogAddOn) {
    if (!canWrite || busy) return;
    setBusy(true);
    try {
      await api.updateAdminAddOn(row.id, { is_active: !row.is_active });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed.');
    } finally {
      setBusy(false);
    }
  }

  async function onDeleteAddOn(id: number) {
    if (!canWrite || busy) return;
    setBusy(true);
    try {
      await api.deleteAdminAddOn(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed.');
    } finally {
      setBusy(false);
    }
  }

  if (!canRead) {
    return (
      <div className="mx-auto max-w-3xl">
        <p className="text-sm text-muted">Admin or auditor access required.</p>
        <Link to="/hub" className="mt-4 inline-block text-sm text-cyan hover:underline">
          Back home
        </Link>
      </div>
    );
  }

  const tabs: Array<{ id: Tab; label: string }> = [
    { id: 'conditions', label: 'Conditions' },
    { id: 'packages', label: 'Packages' },
    { id: 'addons', label: 'Add-ons' },
  ];

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col">
      <PageHeader
        eyebrow="Admin"
        title="Vocab & catalog"
        subtitle={
          canWrite
            ? 'Create, update, and remove conditions, packages, and add-ons.'
            : 'Read-only catalog (auditor).'
        }
      />

      <div className="mt-6 flex flex-wrap gap-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`rounded-full border px-3 py-1.5 text-xs transition ${
              tab === t.id
                ? 'border-cyan/50 bg-cyan/10 text-cyan'
                : 'border-hair text-muted hover:border-cyan/40 hover:text-mist'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <p className="mt-4 rounded-xl border border-rose/40 bg-rose/5 px-4 py-3 text-sm text-rose">
          {error}
        </p>
      )}

      {tab === 'conditions' && (
        <section className="mt-6">
          {canWrite && (
            <form
              onSubmit={(e) => void onCreateCondition(e)}
              className="mb-6 grid gap-3 sm:grid-cols-3"
            >
              <Input
                placeholder="slug"
                value={condSlug}
                onChange={(e) => setCondSlug(e.target.value)}
                required
              />
              <Input
                placeholder="Canonical English name"
                value={condName}
                onChange={(e) => setCondName(e.target.value)}
                required
              />
              <Button type="submit" disabled={busy}>
                Add condition
              </Button>
            </form>
          )}
          <ul className="space-y-2">
            {conditions.map((row) => (
              <li
                key={row.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-hair bg-panel/60 px-4 py-3 text-sm"
              >
                <div>
                  <p className="text-mist">{row.canonical_en}</p>
                  <p className="text-xs text-muted">
                    {row.slug} · {row.active ? 'active' : 'inactive'}
                  </p>
                </div>
                {canWrite && (
                  <div className="flex gap-2">
                    <Button
                      tone="ghost"
                      className="min-h-9 px-3 py-1.5 text-xs"
                      disabled={busy}
                      onClick={() => void onToggleCondition(row)}
                    >
                      {row.active ? 'Deactivate' : 'Activate'}
                    </Button>
                    <Button
                      tone="danger"
                      className="min-h-9 px-3 py-1.5 text-xs"
                      disabled={busy}
                      onClick={() => void onDeleteCondition(row.slug)}
                    >
                      Delete
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {tab === 'packages' && (
        <section className="mt-6">
          {canWrite && (
            <form
              onSubmit={(e) => void onCreatePackage(e)}
              className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5"
            >
              <Input
                placeholder="slug"
                value={pkgSlug}
                onChange={(e) => setPkgSlug(e.target.value)}
                required
              />
              <Input
                placeholder="Name"
                value={pkgName}
                onChange={(e) => setPkgName(e.target.value)}
                required
              />
              <select
                className="min-h-11 rounded-2xl border border-hair bg-elevated px-3 text-sm text-mist"
                value={pkgLevel}
                onChange={(e) => setPkgLevel(e.target.value as typeof pkgLevel)}
              >
                <option value="basic">basic</option>
                <option value="intermediate">intermediate</option>
                <option value="advanced">advanced</option>
              </select>
              <Input
                type="number"
                min="0"
                step="0.01"
                placeholder="Price LKR"
                value={pkgPrice}
                onChange={(e) => setPkgPrice(e.target.value)}
                required
              />
              <Button type="submit" disabled={busy}>
                Add package
              </Button>
            </form>
          )}
          <ul className="space-y-2">
            {packages.map((row) => (
              <li
                key={row.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-hair bg-panel/60 px-4 py-3 text-sm"
              >
                <div>
                  <p className="text-mist">{row.name}</p>
                  <p className="text-xs text-muted">
                    {row.slug} · {row.care_level} · LKR {row.price_lkr} ·{' '}
                    {row.is_active === false ? 'inactive' : 'active'}
                  </p>
                </div>
                {canWrite && (
                  <div className="flex gap-2">
                    <Button
                      tone="ghost"
                      className="min-h-9 px-3 py-1.5 text-xs"
                      disabled={busy}
                      onClick={() => void onTogglePackage(row)}
                    >
                      {row.is_active === false ? 'Activate' : 'Deactivate'}
                    </Button>
                    <Button
                      tone="danger"
                      className="min-h-9 px-3 py-1.5 text-xs"
                      disabled={busy}
                      onClick={() => void onDeletePackage(row.id)}
                    >
                      Delete
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {tab === 'addons' && (
        <section className="mt-6">
          {canWrite && (
            <form
              onSubmit={(e) => void onCreateAddOn(e)}
              className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5"
            >
              <Input
                placeholder="slug"
                value={addonSlug}
                onChange={(e) => setAddonSlug(e.target.value)}
                required
              />
              <Input
                placeholder="Name"
                value={addonName}
                onChange={(e) => setAddonName(e.target.value)}
                required
              />
              <select
                className="min-h-11 rounded-2xl border border-hair bg-elevated px-3 text-sm text-mist"
                value={addonCategory}
                onChange={(e) => setAddonCategory(e.target.value as typeof addonCategory)}
              >
                <option value="hospital">hospital</option>
                <option value="food">food</option>
                <option value="transport">transport</option>
                <option value="supplies">supplies</option>
                <option value="other">other</option>
              </select>
              <Input
                type="number"
                min="0"
                step="0.01"
                placeholder="Price LKR"
                value={addonPrice}
                onChange={(e) => setAddonPrice(e.target.value)}
                required
              />
              <Button type="submit" disabled={busy}>
                Add add-on
              </Button>
            </form>
          )}
          <ul className="space-y-2">
            {addons.map((row) => (
              <li
                key={row.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-hair bg-panel/60 px-4 py-3 text-sm"
              >
                <div>
                  <p className="text-mist">{row.name}</p>
                  <p className="text-xs text-muted">
                    {row.slug} · {row.category} · LKR {row.price_lkr} ·{' '}
                    {row.is_active === false ? 'inactive' : 'active'}
                  </p>
                </div>
                {canWrite && (
                  <div className="flex gap-2">
                    <Button
                      tone="ghost"
                      className="min-h-9 px-3 py-1.5 text-xs"
                      disabled={busy}
                      onClick={() => void onToggleAddOn(row)}
                    >
                      {row.is_active === false ? 'Activate' : 'Deactivate'}
                    </Button>
                    <Button
                      tone="danger"
                      className="min-h-9 px-3 py-1.5 text-xs"
                      disabled={busy}
                      onClick={() => void onDeleteAddOn(row.id)}
                    >
                      Delete
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
