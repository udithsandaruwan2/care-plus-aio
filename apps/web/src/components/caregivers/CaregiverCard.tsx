import { Link } from 'react-router-dom';
import type { CaregiverProfile } from '@care-plus/api-client';
import { Avatar } from '../ui/Avatar';

export function caregiverSummary(cg: CaregiverProfile): string {
  if (cg.bio && cg.bio.trim()) return cg.bio.trim();
  const specialties = (cg.specialties || []).slice(0, 3).join(', ');
  const where = cg.city ? ` around ${cg.city}` : '';
  return specialties
    ? `Supports ${specialties}${where}.`
    : `Community caregiver${where || ' on Care Plus'}.`;
}

function Stars({ average, count }: { average?: number | null; count?: number }) {
  if (!count) {
    return <span className="text-[11px] text-muted">No reviews yet</span>;
  }
  const rounded = Math.round(average ?? 0);
  return (
    <span className="text-[11px] text-amber">
      {'★'.repeat(Math.max(1, Math.min(5, rounded)))}
      <span className="ml-1 text-muted">
        {(average ?? 0).toFixed(1)} ({count})
      </span>
    </span>
  );
}

/** Directory card: photo, name, age, blurb, and a route into the full profile. */
export function CaregiverCard({
  caregiver,
  onHover,
}: {
  caregiver: CaregiverProfile;
  onHover?: (id: number) => void;
}) {
  const specialties = (caregiver.specialties || []).slice(0, 3);
  const unavailable = caregiver.is_available === false;

  return (
    <article
      onMouseEnter={onHover ? () => onHover(caregiver.id) : undefined}
      className="group flex h-full flex-col rounded-2xl border border-hair bg-panel p-5 shadow-[var(--cp-shadow-soft)] transition hover:border-cyan/40"
    >
      <div className="flex items-start gap-4">
        <Avatar name={caregiver.display_name} photoUrl={caregiver.photo_url} size="lg" />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="truncate font-display text-base text-mist">
              {caregiver.display_name}
            </h3>
            <span className="shrink-0 text-sm text-mint" title="Trust score">
              {Math.round((caregiver.trust_score || 0) * 100)}
            </span>
          </div>
          <p className="mt-0.5 truncate text-xs text-muted">
            {[
              caregiver.age ? `${caregiver.age} yrs` : null,
              caregiver.city || null,
              caregiver.years_experience ? `${caregiver.years_experience} yrs exp` : null,
            ]
              .filter(Boolean)
              .join(' · ') || 'Sri Lanka'}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <Stars average={caregiver.review_average} count={caregiver.review_count} />
            {caregiver.is_verified && (
              <span className="rounded-full border border-mint/40 px-2 py-0.5 text-[10px] uppercase tracking-wide text-mint">
                Verified
              </span>
            )}
            {unavailable && (
              <span className="rounded-full border border-hair px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted">
                Unavailable
              </span>
            )}
          </div>
        </div>
      </div>

      <p className="mt-4 line-clamp-3 text-sm leading-relaxed text-mist/80">
        {caregiverSummary(caregiver)}
      </p>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {(specialties.length ? specialties : ['general care']).map((s) => (
          <span
            key={s}
            className="rounded-full border border-hair px-2.5 py-0.5 text-[11px] text-violet"
          >
            {s}
          </span>
        ))}
      </div>

      <p className="mt-3 text-[11px] text-cyan">
        {(caregiver.languages || []).join(' · ') || 'Languages not listed'}
      </p>

      <Link
        to={`/caregivers/${caregiver.id}`}
        className="mt-4 inline-flex min-h-11 items-center justify-center rounded-xl bg-cyan px-5 py-2.5 text-sm font-semibold text-inverse transition hover:brightness-95"
      >
        View profile &amp; book
      </Link>
    </article>
  );
}
