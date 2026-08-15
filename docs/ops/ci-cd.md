# CI/CD (Step 72)

## GitHub Actions

| Workflow | Trigger | Jobs |
|----------|---------|------|
| [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) | PR + push to `main` | Ruff/Black, Prettier, web typecheck, Docker build smoke, Compose backend tests + migrate |
| [`.github/workflows/cd.yml`](../../.github/workflows/cd.yml) | Push to `main` (+ manual) | Build & push `ghcr.io/<owner>/care-plus-backend` (`:latest`, `:<sha>`, `:<short>`) |

CD uses `GITHUB_TOKEN` with `packages: write`. No extra registry secrets required for GHCR under this repo.

## Local parity

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml exec -T backend python manage.py migrate --noinput
docker compose -f infra/docker-compose.yml exec -T backend python manage.py test -v1
curl -fsS http://localhost:8000/api/v1/health/
```

Optional auto-migrate on container start (dev/CI only):

```bash
# in .env
MIGRATE_ON_START=1
```

`backend/entrypoint.sh` runs `migrate --noinput` when that flag is set, then `collectstatic`.

## Pull published image

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u USERNAME --password-stdin
docker pull ghcr.io/udithsandaruwan2/care-plus-backend:latest
```

Tag scheme:

- `latest` — tip of `main`
- full git SHA — immutable
- 7-char short SHA — convenient

## Deploy migrate (production)

Do **not** rely on `MIGRATE_ON_START` in production. After pulling a new image / restarting the API container:

```bash
docker compose exec backend python manage.py migrate --noinput
# or one-shot:
docker compose run --rm backend python manage.py migrate --noinput
```

VM + TLS + image pull: [deploy.md](deploy.md) (Step 73).

## Checklist

- [x] CI runs lint, format, typecheck, image build, Django tests
- [x] CD pushes backend image to GHCR on `main`
- [x] Migrate documented + optional `MIGRATE_ON_START` for local/CI
- [x] Staging sign-off path: pull `:latest`, migrate, health check (`infra/scripts/deploy.sh`)
