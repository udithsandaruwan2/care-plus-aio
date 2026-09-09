import { motion } from "framer-motion";
import { MapPin, Star, UserRound } from "lucide-react";
import type { MatchHit, MatchResponse } from "@care-plus/api-client";

function formatDistance(meters: number | null | undefined): string {
  if (meters == null || Number.isNaN(meters)) return "—";
  if (meters < 1000) return `${Math.round(meters)} m`;
  return `${(meters / 1000).toFixed(1)} km`;
}

function shortXai(hit: MatchHit): string {
  const raw = hit.explanation?.trim() || "";
  if (!raw) {
    const specs = hit.specialties.slice(0, 2).join(", ");
    return specs ? `Strong on ${specs}` : "Ranked by VEHMF fit";
  }
  return raw.length > 120 ? `${raw.slice(0, 117)}…` : raw;
}

function MatchCard({ hit }: { hit: MatchHit }) {
  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="border border-cyan/25 bg-background/55 p-3 backdrop-blur-sm"
    >
      <div className="flex items-start gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center border border-cyan/40 bg-cyan/10 text-cyan">
          {hit.photo_url ? (
            <img
              src={hit.photo_url}
              alt=""
              className="size-full object-cover"
            />
          ) : (
            <UserRound className="size-5" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2">
            <h3 className="truncate font-mono text-xs font-semibold text-foreground">
              #{hit.rank} {hit.display_name}
            </h3>
            <span className="shrink-0 font-mono text-[10px] text-cyan">
              {(hit.score * 100).toFixed(0)}%
            </span>
          </div>
          <p className="mt-1 line-clamp-2 font-mono text-[10px] leading-relaxed text-muted-foreground">
            {shortXai(hit)}
          </p>
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[9px] uppercase text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <MapPin className="size-3 text-cyan/70" />
              {formatDistance(hit.distance_m)}
            </span>
            {hit.trust_score != null && (
              <span className="inline-flex items-center gap-1">
                <Star className="size-3 text-violet" />
                Trust {hit.trust_score.toFixed(1)}
              </span>
            )}
            {hit.specialties.slice(0, 2).map((s) => (
              <span key={s} className="text-cyan/80">
                {s}
              </span>
            ))}
          </div>
        </div>
      </div>
    </motion.article>
  );
}

export function MatchRail({
  match,
  onClear,
}: {
  match: MatchResponse;
  onClear?: () => void;
}) {
  const hits = match.results.slice(0, 5);
  if (!hits.length) return null;

  return (
    <motion.section
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="mx-auto mb-4 w-full max-w-3xl border border-cyan/20 bg-card/40"
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <div>
          <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-cyan/80">
            VEHMF match rail
          </p>
          <p className="font-mono text-[10px] text-muted-foreground">
            {hits.length} caregivers · {Math.round(match.latency_ms)} ms
            {match.query ? ` · “${match.query.slice(0, 48)}”` : ""}
          </p>
        </div>
        {onClear && (
          <button
            type="button"
            onClick={onClear}
            className="font-mono text-[9px] uppercase tracking-wider text-cyan hover:underline"
          >
            New request
          </button>
        )}
      </div>
      <div className="grid gap-2 p-3 sm:grid-cols-2">
        {hits.map((hit) => (
          <MatchCard key={hit.caregiver_id} hit={hit} />
        ))}
      </div>
    </motion.section>
  );
}
