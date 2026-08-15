# Backups (Step 75)

Lean profile: one VM, Docker volumes for Postgres, Redis AOF, and FAISS/ML
artifacts. Run these **on the VM** (or any host running prod Compose).

Schedule: **daily** DB dump (keep 7 days); **weekly** copy of `ml_data`.
Store copies **off-box** (object storage / encrypted USB), not only on the VM.

## Postgres (Timescale / PostGIS)

```bash
# from repo root, with .env loaded
set -a && source .env && set +a
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="${BACKUP_DIR:-./var/backups}/pg-${STAMP}.sql.gz"
mkdir -p "$(dirname "$OUT")"

docker compose -f infra/docker-compose.prod.yml --env-file .env exec -T db \
  pg_dump -U "${POSTGRES_USER:-careplus}" -d "${POSTGRES_DB:-careplus}" \
  --no-owner --format=plain \
  | gzip > "$OUT"

ls -lh "$OUT"
```

Restore (destroys current DB contents — take a fresh dump first):

```bash
gunzip -c pg-YYYYMMDDTHHMMSSZ.sql.gz \
  | docker compose -f infra/docker-compose.prod.yml --env-file .env exec -T db \
    psql -U "${POSTGRES_USER:-careplus}" -d "${POSTGRES_DB:-careplus}"
```

Helper: [`infra/scripts/backup.sh`](../../infra/scripts/backup.sh).

## Redis

AOF is enabled (`--appendonly yes`). Volume `redis_data` is the live file.
A dump is optional:

```bash
docker compose -f infra/docker-compose.prod.yml exec -T redis redis-cli BGREWRITEAOF
# then copy the named volume, or:
docker compose -f infra/docker-compose.prod.yml cp redis:/data/appendonlydir "./var/backups/redis-${STAMP}"
```

Redis is cache + broker + locks. Losing it is painful (sessions/jobs) but
**Postgres is the source of truth** for accounts, matches, records.

## ML artifacts (FAISS / CF)

Prod mounts volume `ml_data` at `/ml`. After `build_caregiver_index` / `train_cf`:

```bash
docker compose -f infra/docker-compose.prod.yml cp backend:/ml "./var/backups/ml-${STAMP}"
```

## What not to back up into git

`.env`, `DJANGO_SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, Sentry DSN, GHCR tokens,
VAPID keys, PayHere secrets.
