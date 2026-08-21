/** Visible badge when rendered data is cached / stale-offline (Step 94 / 98). */

export function CacheSourceBadge({
  fromCache,
  stale,
  provisional = false,
  className = '',
}: {
  fromCache: boolean;
  stale: boolean;
  /** Step 98 — on-device HashEmbedder ranking, not VEHMF. */
  provisional?: boolean;
  className?: string;
}) {
  if (!fromCache && !stale && !provisional) return null;
  const label = provisional
    ? 'Provisional · on-device'
    : stale
      ? 'Cached · may be out of date'
      : 'Cached';
  return (
    <span
      role="status"
      className={
        className ||
        'inline-flex items-center rounded-full border border-amber/40 bg-amber/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-100'
      }
    >
      {label}
    </span>
  );
}
