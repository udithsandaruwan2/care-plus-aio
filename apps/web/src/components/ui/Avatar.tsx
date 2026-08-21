import { useState } from 'react';
import { mediaUrl } from '../../lib/mediaUrl';

type Size = 'sm' | 'md' | 'lg' | 'xl';

const SIZE_CLASS: Record<Size, string> = {
  sm: 'h-10 w-10 text-xs',
  md: 'h-14 w-14 text-sm',
  lg: 'h-20 w-20 text-lg',
  xl: 'h-32 w-32 text-3xl',
};

export function initialsOf(name: string): string {
  const parts = (name || '').replace(/-/g, ' ').split(' ').filter(Boolean);
  if (!parts.length) return 'CP';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Profile photo with a graceful initials fallback (signed URLs can expire). */
export function Avatar({
  name,
  photoUrl,
  size = 'md',
  className = '',
}: {
  name: string;
  photoUrl?: string | null;
  size?: Size;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const src = failed ? undefined : mediaUrl(photoUrl);
  const base = `${SIZE_CLASS[size]} shrink-0 overflow-hidden rounded-2xl border border-hair ${className}`;

  if (!src) {
    return (
      <div
        aria-hidden="true"
        className={`${base} flex items-center justify-center bg-soft font-display text-muted`}
      >
        {initialsOf(name)}
      </div>
    );
  }

  return (
    <img
      src={src}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
      className={`${base} bg-soft object-cover`}
    />
  );
}
