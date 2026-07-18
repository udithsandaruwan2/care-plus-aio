# Care Plus — Progress Log

> **Purpose:** running record of _what's done_ and _what's next_, so work can resume
> from any device. Committed to git (syncs across machines). Updated **feature by feature**.
> Full plan: [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) ·
> Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) ·
> Frontend: [docs/FRONTEND.md](docs/FRONTEND.md)

_Last updated: 2026-07-18 — Milestone M0 complete (Steps 1–5)._

---

## How to resume on a new device

```bash
git clone https://github.com/udithsandaruwan2/care-plus-aio.git "Care Plus"
cd "Care Plus"
cp .env.example .env                      # fill in secrets (GEMINI_API_KEY, etc.)
docker compose -f infra/docker-compose.yml up -d --build
curl -fsS http://localhost:8000/api/v1/health/   # expect {"status":"ok","db":"ok","redis":"ok"}
```

Notes:

- Backend runs in Docker on **Python 3.11** (host Python version irrelevant).
- Host DB port is **5433** (container internal 5432) to avoid clashing with a local Postgres.
- Requires Docker + ~5–10 GB free disk. Images: `timescale/timescaledb-ha:pg16`, `redis:7-alpine`.

---

## Decisions locked (lean profile)

ASR = Web Speech + `faster-whisper` fallback · CF = `implicit` ALS (→ LightFM) ·
Time-series = TimescaleDB · Embeddings = `intfloat/multilingual-e5-base` (768-d) ·
Hosting = single VM + Docker Compose. See DEVELOPMENT_PLAN §0.

---

## Status board

Legend: ✅ done · 🔜 next · ⬜ pending · 🚫 blocked

### M0 · Foundations

- ✅ **Step 1** — Repo & monorepo skeleton (pnpm/turbo, dirs, `.env.example`). commit `ced6d2d`
- ✅ **Step 2** — Docker infra: TimescaleDB+PostGIS+pgcrypto + Redis; extensions verified.
- ✅ **Step 3** — Dockerized Django+DRF skeleton; `/api/v1/health/` green; Swagger at `/api/docs/`. commit `322f99a`
- ✅ **Step 4** — Channels `ws/ping` echo consumer + Celery worker + `debug_task` (both verified).
- ✅ **Step 5** — Quality gates: Ruff+Black (py), Prettier+ESLint (js), pre-commit, GitHub Actions CI. **M0 complete.**

### M1 · Auth & Consent

- ⬜ Step 6 — Custom user + JWT + RBAC roles
- ⬜ Step 7 — Consent engine (PDPA/GDPR gate)
- ⬜ Step 8 — Immutable audit trail

### M2 · Web shell + Neural Core

- ⬜ Step 9 — Shared packages + Vite React app bootstrap
- ⬜ Step 10 — Auth screens + API client
- ⬜ Step 11 — Neural Core audio-reactive brain (R3F + Bloom)
- ⬜ Step 12 — Assistant FSM + Goal Ring + realtime feedback shell

### M3 · Voice → Intent

- ⬜ Step 13 — Mic capture + live transcript (Web Speech)
- ⬜ Step 14 — Gemini structured-output intent extraction (backend)
- ⬜ Step 15 — Entity chips + Goal Ring fill (end-to-end)

### M4 · VEHMF v1 + Match UX

- ⬜ Step 16 — Domain models + seed data
- ⬜ Step 17 — Embeddings + FAISS index build
- ⬜ Step 18 — AHP weights
- ⬜ Step 19 — VEHMF engine (CBF+Geo+Trust+fusion+XAI)
- ⬜ Step 20 — Match over WebSocket + result UX

### M5 · Personalization

- ⬜ Step 21 — CF training (offline) · ⬜ Step 22 — Blend CF into fusion

### M6 · Health monitoring

- ⬜ Step 23 — Timescale hypertable + ingest · ⬜ Step 24 — Anomaly daemon
- ⬜ Step 25 — Dynamic re-weight + emergency re-match · ⬜ Step 26 — Alerts UX + push

### M7 · Scheduling

- ⬜ Step 27 — Shift model + calendar · ⬜ Step 28 — Redlock booking · ⬜ Step 29 — Conflict fallback

### M8 · Mobile app (Expo RN)

- ⬜ Steps 30–34 — bootstrap → auth → Neural Core (Skia) → voice→match parity → push

### M9 · Compliance & hardening

- ⬜ Steps 35–37 — pgcrypto columns · erasure/export · TLS + load tests

### M10 · Ship

- ⬜ Steps 38–40 — CI/CD · deploy to VM · store submissions

---

## Changelog (newest first)

- **Step 5** — Ruff+Black (`backend/pyproject.toml`), Prettier + flat ESLint config, `.pre-commit-config.yaml`, GitHub Actions CI (backend lint · prettier · docker build). Lint/format verified clean.
- **Step 4** — ASGI `ProtocolTypeRouter` (HTTP+WebSocket); `ws/ping` echo consumer; Celery app on Redis + `debug_task`; `worker` service in Compose.
- **Step 3** — Django 4.2 + DRF + GeoDjango skeleton, split settings, health endpoint (DB+Redis), Swagger; backend service in Compose. `322f99a`
- **Step 2** — `infra/docker-compose.yml` (TimescaleDB-HA + Redis) + init SQL (postgis/timescaledb/pgcrypto); host DB port → 5433.
- **Step 1** — Monorepo skeleton, workspace config, `.env.example`. `ced6d2d`
- **Docs** — ARCHITECTURE.md, FRONTEND.md, DEVELOPMENT_PLAN.md; connected `origin/main`.
