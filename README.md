# Care Plus

**Care Plus** is a research-grade, data-driven AI ecosystem that matches **patients** with
**caregivers** using multilingual (Sinhala / Tamil / English) **voice input**, a hybrid
recommendation engine (**VEHMF**), and **real-time health monitoring** that dynamically
re-ranks matches during medical anomalies.

Built for **speed** (VEHMF ranked list **p95 < 800 ms** of engine time) and **resource efficiency**
(the lean stack fits in **≤ 4 GB RAM / 2 vCPU**, no GPU required at runtime). Full voice turns
(ASR + intent + chat + TTS) are timed per stage on `POST /voice/turn/` (`timings.*_ms`) and are
typically longer than the match engine itself.

---

## The three research capabilities

| #   | Capability                      | What it does                                                                                           |
| --- | ------------------------------- | ------------------------------------------------------------------------------------------------------ |
| 1   | **Hybrid Voice → Match**        | A spoken Sinhala sentence becomes a mathematically ranked, _explainable_ caregiver list.               |
| 2   | **Health Anomaly → Re-Match**   | Wearable time-series triggers dynamic weight shifts so medical fit overrides logistics in emergencies. |
| 3   | **Concurrency-safe Scheduling** | Distributed locking guarantees no double-booking.                                                      |

## Architecture at a glance

```
Perception (edge voice + IoT)  →  Cognitive (Django + Gemini 1.5 Flash)
        →  Decision Engine (VEHMF: FAISS + CF + Geo + AHP fusion)
        →  State & Execution (PostgreSQL/PostGIS/TimescaleDB + Redis + Celery + FCM)
```

The stack ships in **two profiles**:

- **Lean profile** (build first): modular monolith, one Postgres, Redis-for-everything, no GPU.
- **Full profile** (north-star): microservices, FAISS-HNSW, RabbitMQ, InfluxDB.

## Experience — the "Neural Core" assistant

The signature UI is a **realtime, audio-reactive glowing brain**: it pulses to your voice,
visibly "thinks" (color-coded states), fills a **Goal Ring** as it captures your intent, and
streams live transcript + entity chips — all in the sci-fi **"Aurora Neural"** dark theme.
Delivered on **web** (React + WebGL/react-three-fiber) and **mobile** (Expo React Native + Skia),
Android and iOS. Full design in [docs/FRONTEND.md](docs/FRONTEND.md).

## Documentation

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — backend/system deep-dive: layers, framework
  mapping, data flows, VEHMF code-level design, data model, API contract, security,
  performance/resource budgets, deployment, and a phased roadmap.
- **[docs/FRONTEND.md](docs/FRONTEND.md)** — web + mobile blueprint: the Aurora Neural design
  system, the Neural Core voice-assistant + state machine, web/mobile architecture, screen
  inventory, realtime contract, and efficiency rules.
- **[docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)** — v0.3 product build plan (M0–M17,
  Steps 1–75), complete on `main`.
- **[docs/DEVELOPMENT_PLAN_V2.md](docs/DEVELOPMENT_PLAN_V2.md)** — v0.4 engine plan (M18–M24,
  Steps 76–106), **complete**: telemetry and audit, streaming conversation, offline support,
  AI decision history, and a ranking loop that learns from its outcomes.

## Status

**v0.3** (M0–M17 / Steps 1–75) and **v0.4** (M18–M24 / Steps 76–106) are **complete** on `main`.
Testers use **web** and **Expo Go** (SDK 54). Play/App Store submissions are deferred until store
accounts exist. See [PROGRESS.md](PROGRESS.md) and [docs/ops/launch-checklist.md](docs/ops/launch-checklist.md).

## Quick start (local)

One-shot (API + Celery + migrate + seed + web):

```bash
cp -n .env.example .env   # once; add GEMINI_API_KEY if you want live NLP/TTS
./scripts/run-local.sh
```

Or step by step:

```bash
# Backend (TimescaleDB + Redis + Django + Celery)
docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml exec -T backend python manage.py migrate --noinput
docker compose -f infra/docker-compose.yml exec -T backend python manage.py seed_demo
curl -fsS http://localhost:8000/api/v1/health/

# Web
pnpm install
pnpm --filter @care-plus/web dev --host 127.0.0.1 --port 5173
```

| Surface | URL |
| ------- | --- |
| Web app | http://127.0.0.1:5173 |
| API     | http://127.0.0.1:8000/api/v1/ |
| Health  | http://127.0.0.1:8000/api/v1/health/ |

**Demo logins** (password `CarePlus!demo`):

| Email | Role |
| ----- | ---- |
| `demo.patient@careplus.local` | Patient (active care + Serah) |
| `demo.caregiver@careplus.local` | Caregiver inbox / schedule |
| `demo.admin@careplus.local` | Admin hub |

Production / TLS / backups: [docs/ops/deploy.md](docs/ops/deploy.md).

## Tech stack (lean profile)

**Backend:** Django 4.2 · DRF · Channels (ASGI) · Gemini 1.5 Flash · FAISS · LightFM/implicit ·
NumPy/SciPy (AHP) · PostgreSQL + PostGIS + TimescaleDB · Redis · Celery · Firebase FCM.

**Web:** Vite · React 18 · TypeScript · Tailwind · Framer Motion · react-three-fiber (Neural Core) · Zustand · TanStack Query.

**Mobile:** Expo · React Native · TypeScript · react-native-skia · Reanimated · expo-notifications (Android + iOS).

**Shared:** pnpm workspaces + Turborepo monorepo (`packages/ui-tokens`, `api-client`, `core`).
