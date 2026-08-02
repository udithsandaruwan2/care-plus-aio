#!/bin/sh
# Collect admin / DRF static assets so WhiteNoise can serve them under uvicorn.
# Optional auto-migrate for local/CI (set MIGRATE_ON_START=1). Production should
# run ``manage.py migrate`` explicitly during deploy (see docs/ops/ci-cd.md).
set -e
if [ "${MIGRATE_ON_START:-0}" = "1" ]; then
  python manage.py migrate --noinput
fi
python manage.py collectstatic --noinput
exec "$@"
