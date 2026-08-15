# Deploy VM + observability (Step 73)

Lean profile: **one Ubuntu VM** (ap-south / Colombo-adjacent), Docker Compose,
Caddy for TLS 1.3, GHCR image pull, Sentry, Prometheus scrape, JSON logs.

## Topology

```
Internet → :443 Caddy (TLS 1.3) → backend:8000 (uvicorn, loopback-published)
                ↘ worker / beat → Redis + TimescaleDB
```

uvicorn is published as `127.0.0.1:8000` only. Public traffic goes through Caddy.

## VM bootstrap

1. Ubuntu 22.04/24.04, 2 vCPU / 4 GB RAM (lean budget).
2. Install Docker Engine + Compose plugin.
3. Clone this repo (or copy `infra/` + `.env`).
4. Copy `.env.example` → `.env` and set production values:

```bash
DJANGO_SETTINGS_MODULE=careplus.settings.prod
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=…          # long random
DJANGO_ALLOWED_HOSTS=app.careplus.lk
CORS_ALLOWED_ORIGINS=https://app.careplus.lk
CSRF_TRUSTED_ORIGINS=https://app.careplus.lk
FRONTEND_BASE_URL=https://app.careplus.lk
POSTGRES_PASSWORD=…          # strong
CADDY_SITE=app.careplus.lk
ACME_EMAIL=ops@careplus.lk
SENTRY_DSN=https://…@sentry.io/…
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
METRICS_TOKEN=…              # scrape /api/v1/metrics/
MIGRATE_ON_START=0
```

5. Point the domain **A record** at the VM. Open **80/443** (and SSH). Do not open 5433/6379/8000 publicly.
6. Login to GHCR and deploy:

```bash
export GHCR_USER=YOUR_GITHUB_USER
export GHCR_TOKEN=ghp_…      # packages:read
chmod +x infra/scripts/deploy.sh
./infra/scripts/deploy.sh
```

The script: `docker login` (if token set) → `compose pull` → `up -d` →
`migrate --noinput` → `GET /api/v1/health/` inside the backend container.

Manual equivalent:

```bash
docker compose -f infra/docker-compose.prod.yml --env-file .env pull
docker compose -f infra/docker-compose.prod.yml --env-file .env up -d
docker compose -f infra/docker-compose.prod.yml --env-file .env \
  run --rm --no-deps backend python manage.py migrate --noinput
docker compose -f infra/docker-compose.prod.yml exec -T backend \
  curl -fsS http://127.0.0.1:8000/api/v1/health/
```

Do **not** set `MIGRATE_ON_START=1` in production.

## TLS (Caddy)

[`infra/caddy/Caddyfile`](../../infra/caddy/Caddyfile) terminates TLS 1.3, forwards
`Host` / `X-Forwarded-Proto` / `X-Forwarded-For`, and upgrades WebSockets
(`/ws/…`) automatically.

- Production hostname: `CADDY_SITE=app.careplus.lk` (Let's Encrypt via ACME).
- HTTP-only staging: `CADDY_SITE=http://localhost` or `http://<vm-ip>`.

Django prod settings already enable HSTS, secure cookies, and
`SECURE_PROXY_SSL_HEADER`. Details: [tls-proxy.md](tls-proxy.md).

## Observability

| Signal | Where |
|--------|--------|
| **Logs** | Docker `json-file` (10m × 5 files). Django prod uses JSON lines (`ts`, `level`, `logger`, `msg`, `request_id`). `docker compose logs -f backend` |
| **Metrics** | `GET /api/v1/metrics/` (Prometheus text). If `METRICS_TOKEN` is set, send `Authorization: Bearer …` or `X-Metrics-Token`. Counters: `careplus_http_requests_total`, histogram `careplus_http_request_duration_seconds` (match p95 target 800 ms is a histogram bucket). |
| **Errors** | Sentry (`SENTRY_DSN`). Django + Celery integrations. Empty DSN = no-op. |
| **Liveness** | `GET /api/v1/health/` → `{status, db, redis, sentry}` |

Example scrape (Prometheus on the VM or a sidecar):

```yaml
scrape_configs:
  - job_name: careplus
    metrics_path: /api/v1/metrics/
    authorization:
      credentials: '<METRICS_TOKEN>'
    static_configs:
      - targets: ['127.0.0.1:8000']
```

## Staging sign-off

- [ ] Pull `ghcr.io/udithsandaruwan2/care-plus-backend:latest`
- [ ] `migrate --noinput`
- [ ] `GET /api/v1/health/` returns `"status":"ok"` and `"sentry":"on"` when DSN is set
- [ ] `GET /api/v1/metrics/` returns Prometheus text (with token if configured)
- [ ] HTTPS on `CADDY_SITE` (or HTTP staging URL) reaches the API
- [ ] Force an error in staging and confirm a Sentry event (optional)

## Rollback

```bash
export CAREPLUS_IMAGE=ghcr.io/udithsandaruwan2/care-plus-backend:<previous-sha>
./infra/scripts/deploy.sh
```

Images are tagged `:latest`, full git SHA, and 7-char short SHA ([ci-cd.md](ci-cd.md)).

Backups: [backups.md](backups.md). Launch ticks: [launch-checklist.md](launch-checklist.md). Mobile: [mobile-expo.md](mobile-expo.md).
