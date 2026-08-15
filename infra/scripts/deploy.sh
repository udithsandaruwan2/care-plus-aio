#!/usr/bin/env bash
# Pull GHCR image, restart prod Compose, migrate, health-check (Step 73).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE=(docker compose -f "$ROOT/infra/docker-compose.prod.yml" --env-file "$ROOT/.env")

if [[ ! -f "$ROOT/.env" ]]; then
  echo "missing $ROOT/.env — copy .env.example and fill production secrets" >&2
  exit 1
fi

# Optional GHCR login when CAREPLUS_IMAGE points at ghcr.io
if [[ -n "${GHCR_TOKEN:-}" && -n "${GHCR_USER:-}" ]]; then
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
fi

"${COMPOSE[@]}" pull
"${COMPOSE[@]}" up -d --remove-orphans
"${COMPOSE[@]}" run --rm --no-deps backend python manage.py migrate --noinput

echo "waiting for health…"
ok=0
for i in $(seq 1 36); do
  if "${COMPOSE[@]}" exec -T backend curl -fsS http://127.0.0.1:8000/api/v1/health/ >/tmp/careplus-health.json; then
    cat /tmp/careplus-health.json
    echo
    ok=1
    break
  fi
  echo "waiting ($i)…"
  sleep 5
done

if [[ "$ok" -ne 1 ]]; then
  echo "health check failed" >&2
  "${COMPOSE[@]}" logs --no-color --tail=80 backend || true
  exit 1
fi

echo "deploy ok"
