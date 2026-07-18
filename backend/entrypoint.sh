#!/bin/sh
# Collect admin / DRF static assets so WhiteNoise can serve them under uvicorn.
set -e
python manage.py collectstatic --noinput
exec "$@"
