import type { CarePackage, CatalogAddOn, SerahAction } from '@care-plus/api-client';

function norm(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

export type ResolvePackageOpts = {
  packageId?: string | number | null;
  nameQuery?: string | null;
  rank?: number | null;
};

/** Map package id / slug / spoken name / index → a catalog package. */
export function resolvePackage(
  packages: CarePackage[] | null | undefined,
  opts: ResolvePackageOpts = {},
): CarePackage | null {
  const rows = [...(packages || [])].sort(
    (a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.id - b.id,
  );
  if (!rows.length) return null;

  const rawId = opts.packageId;
  if (rawId != null && rawId !== '') {
    if (typeof rawId === 'number' || /^\d+$/.test(String(rawId).trim())) {
      const id = Number(rawId);
      const byId = rows.find((p) => p.id === id);
      if (byId) return byId;
    }
    const key = norm(String(rawId));
    const bySlugOrName = rows.find(
      (p) => norm(p.slug) === key || norm(p.name) === key || norm(p.name).includes(key),
    );
    if (bySlugOrName) return bySlugOrName;
  }

  if (opts.rank != null && opts.rank >= 1 && opts.rank <= rows.length) {
    return rows[opts.rank - 1] ?? null;
  }

  const q = norm(opts.nameQuery || '');
  if (q) {
    const qTokens = new Set(q.split(' ').filter((t) => t.length > 1));
    let best: CarePackage | null = null;
    let bestScore = 0;
    for (const row of rows) {
      const name = norm(row.name);
      const slug = norm(row.slug);
      const level = norm(row.care_level);
      if (!name) continue;
      if (name === q || slug === q || name.includes(q) || q.includes(name) || slug.includes(q)) {
        return row;
      }
      // "basic" / "standard" / "intermediate" / "advanced" shortcuts.
      if (q === level || (q === 'standard' && level === 'basic')) return row;
      const hay = `${name} ${slug} ${level}`;
      const hayTokens = new Set(hay.split(' ').filter((t) => t.length > 1));
      if (!qTokens.size || !hayTokens.size) continue;
      let overlap = 0;
      for (const t of qTokens) if (hayTokens.has(t)) overlap += 1;
      const score = overlap / qTokens.size;
      if (score > bestScore && score >= 0.4) {
        bestScore = score;
        best = row;
      }
    }
    if (best) return best;
  }

  return null;
}

export function resolvePackageFromAction(
  packages: CarePackage[] | null | undefined,
  action: Pick<SerahAction, 'package_id' | 'name_query' | 'rank'> | null | undefined,
): CarePackage | null {
  if (!action) return null;
  const hit = resolvePackage(packages, {
    packageId: action.package_id,
    nameQuery: action.name_query,
    rank: action.rank,
  });
  if (hit) return hit;
  const rows = packages || [];
  if (
    !action.name_query &&
    action.package_id == null &&
    action.rank == null &&
    rows.length
  ) {
    return [...rows].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))[0] ?? null;
  }
  return null;
}

/** Resolve spoken add-on names / ids against the catalog. */
export function resolveAddOns(
  addons: CatalogAddOn[] | null | undefined,
  opts: { addonIds?: number[] | null; addonQuery?: string | null; nameQuery?: string | null } = {},
): CatalogAddOn[] {
  const rows = addons || [];
  if (!rows.length) return [];
  const found = new Map<number, CatalogAddOn>();

  for (const id of opts.addonIds || []) {
    const row = rows.find((a) => a.id === id);
    if (row) found.set(row.id, row);
  }

  const q = norm([opts.addonQuery, opts.nameQuery].filter(Boolean).join(' '));
  if (!q) return [...found.values()];

  const aliases: Record<string, string[]> = {
    meal: ['meal', 'meals', 'food', 'nutrition'],
    hospital: ['hospital', 'escort'],
    transport: ['transport', 'clinic transport', 'ride'],
    supplies: ['supplies', 'kit', 'hygiene'],
    physio: ['physio', 'physiotherapy', 'rehab'],
    overnight: ['overnight', 'night watch', 'night'],
  };

  for (const row of rows) {
    const name = norm(row.name);
    const slug = norm(row.slug);
    const cat = norm(row.category);
    if (name && (q.includes(name) || name.includes(q))) {
      found.set(row.id, row);
      continue;
    }
    if (slug && q.includes(slug.replace(/-/g, ' '))) {
      found.set(row.id, row);
      continue;
    }
    for (const [key, words] of Object.entries(aliases)) {
      if (words.some((w) => q.includes(w)) && (slug.includes(key) || name.includes(key) || cat.includes(key) || cat.includes(words[0]!))) {
        found.set(row.id, row);
      }
    }
    // "add meals" / food category
    if (/\b(meal|meals|food)\b/.test(q) && cat === 'food') found.set(row.id, row);
  }

  return [...found.values()];
}

/** Pull an explicit day count from spoken text ("7 days", "for a week"). */
export function parseDaysFromText(text: string | null | undefined): number | null {
  const raw = (text || '').toLowerCase();
  if (!raw.trim()) return null;
  const m = raw.match(/\b(\d{1,3})\s*(?:day|days)\b/);
  if (m) {
    const n = Number(m[1]);
    if (Number.isFinite(n) && n >= 1 && n <= 365) return n;
  }
  if (/\b(a\s+)?week\b|\bseven\s+days\b/.test(raw)) return 7;
  if (/\b(a\s+)?fortnight\b|\btwo\s+weeks?\b/.test(raw)) return 14;
  if (/\b(a\s+)?month\b|\bthirty\s+days\b/.test(raw)) return 30;
  if (/\bfive\s+days\b/.test(raw)) return 5;
  if (/\bten\s+days\b/.test(raw)) return 10;
  return null;
}
