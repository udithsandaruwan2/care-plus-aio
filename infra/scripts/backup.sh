#!/usr/bin/env bash
# Daily-ish Postgres dump for prod Compose (Step 75). See docs/ops/backups.md.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE=(docker compose -f "$ROOT/infra/docker-compose.prod.yml" --env-file "$ROOT/.env")

if [[ ! -f "$ROOT/.env" ]]; then
  echo "missing $ROOT/.env" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${BACKUP_DIR:-$ROOT/var/backups}"
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/pg-${STAMP}.sql.gz"

"${COMPOSE[@]}" exec -T db \
  pg_dump -U "${POSTGRES_USER:-careplus}" -d "${POSTGRES_DB:-careplus}" \
  --no-owner --format=plain \
  | gzip > "$OUT"

# Keep 7 newest dumps in this directory.
ls -1t "$OUT_DIR"/pg-*.sql.gz 2>/dev/null | tail -n +8 | xargs -r rm -f

ls -lh "$OUT"
echo "backup ok"
