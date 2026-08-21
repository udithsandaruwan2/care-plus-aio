/** Visible badge when rendered data is cached / stale-offline (Step 94). */

export function CacheSourceBadge({
  fromCache,
  stale,
  className = '',
}: {
  fromCache: boolean;
  stale: boolean;
  className?: string;
}) {
  if (!fromCache && !stale) return null;
  const label = stale ? 'Cached · may be out of date' : 'Cached';
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
