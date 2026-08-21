#!/usr/bin/env bash
# Run the complete Care Plus stack locally (API + workers + web).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Docker (db, redis, backend, worker, beat)"
docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml exec -T backend python manage.py migrate --noinput
docker compose -f infra/docker-compose.yml exec -T backend python manage.py seed_demo

echo "==> Health"
curl -fsS http://localhost:8000/api/v1/health/
echo

echo "==> Web (pnpm)"
if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm not found. Install Node 20+ and pnpm 9, then re-run." >&2
  exit 1
fi
pnpm install
echo "Starting web on http://127.0.0.1:5173  (API http://127.0.0.1:8000)"
echo "Demo: demo.patient@careplus.local / CarePlus!demo"
exec pnpm --filter @care-plus/web dev --host 127.0.0.1 --port 5173
