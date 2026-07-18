# Care Plus — Step-by-Step Development Plan

> **Status:** Active build plan (v0.1) — the execution companion to
> [ARCHITECTURE.md](ARCHITECTURE.md) and [FRONTEND.md](FRONTEND.md).
> **How to use:** we build **one numbered step at a time**. Each step has a **Goal**,
> concrete **Tasks**, **Commands**, and an **✅ Acceptance criterion**. We do not start a step
> until the previous one's acceptance passes. This keeps momentum, working software, and
> reviewable diffs at every point.

---

## 0. Decisions Locked (lean profile defaults)

We start on the **Lean profile** ([ARCHITECTURE.md §4](ARCHITECTURE.md#4-technology-stack--two-profiles-lean-vs-full)). All are reversible.

| #   | Decision        | Locked default                                                                                    | Note                          |
| --- | --------------- | ------------------------------------------------------------------------------------------------- | ----------------------------- |
| 1   | ASR             | Client **Web Speech API** (web) / on-device voice (mobile) **+ server `faster-whisper` fallback** | No GPU at runtime.            |
| 2   | CF library      | Pluggable `CFModel` interface; MVP = **`implicit` (ALS)**, upgrade path = LightFM                 | Easier to install, swappable. |
| 3   | Time-series     | **TimescaleDB** (Postgres extension)                                                              | One DB to run/secure.         |
| 4   | Embeddings      | **`intfloat/multilingual-e5-base`** (768-d, multilingual incl. Sinhala/Tamil)                     | Feeds FAISS.                  |
| 5   | Hosting         | **Single VM + Docker Compose**, region **ap-south (Mumbai)** for PDPA proximity                   | Provider TBD.                 |
| —   | Backend runtime | **Docker, Python 3.11** (host is 3.14 → too new for some ML wheels)                               | Host Python irrelevant.       |
| —   | Node/JS         | **Node 22 + pnpm via Corepack** (monorepo)                                                        | `corepack enable`.            |

> Change any of these anytime; the plan and scaffold adapt.

---

## Environment prerequisites (already verified on this machine)

Docker 29 + Compose v5 · Node 22 · npm 11 · git 2.53 · psql 14. `pnpm` enabled via `corepack enable`.

---

## Milestone map

| Milestone                        | Steps | Outcome                                                            |
| -------------------------------- | ----- | ------------------------------------------------------------------ |
| **M0 · Foundations**             | 1–5   | Monorepo + Django API + DB + Docker all boot; health check green.  |
| **M1 · Auth & Consent**          | 6–8   | JWT auth, RBAC roles, consent gate, audit log.                     |
| **M2 · Web shell + Neural Core** | 9–12  | React app, Aurora Neural theme, audio-reactive brain, FSM.         |
| **M3 · Voice → Intent**          | 13–15 | Mic capture, Gemini structured JSON, entity chips + Goal Ring.     |
| **M4 · VEHMF v1 + Match UX**     | 16–20 | FAISS CBF + AHP fusion + geo + XAI; ranked results over WebSocket. |
| **M5 · Personalization (CF)**    | 21–22 | Offline-trained CF blended into fusion.                            |
| **M6 · Health monitoring**       | 23–26 | Timescale ingest, anomaly daemon, dynamic re-match, alerts.        |
| **M7 · Scheduling**              | 27–29 | Redlock booking, conflict fallback.                                |
| **M8 · Mobile app**              | 30–34 | Expo RN app reaching feature parity for patient flow.              |
| **M9 · Compliance & hardening**  | 35–37 | Encryption, full audit, erasure, TLS, load tests.                  |
| **M10 · Ship**                   | 38–40 | CI/CD, deploy to VM, store submissions.                            |

---

## M0 · Foundations

### Step 1 — Repository & monorepo skeleton

**Goal:** one repo, workspace tooling, no app code yet.
**Tasks:** `git init`; create `pnpm-workspace.yaml`, `turbo.json`, root `package.json`, `.gitignore`, `.editorconfig`, `.env.example`; create empty `apps/`, `packages/`, `backend/`, `ml/`, `infra/`.
**Commands:**

```bash
corepack enable
git init && git add -A && git commit -m "chore: repo skeleton"
```

**✅ Acceptance:** `git status` clean; folder tree matches [ARCHITECTURE.md §14](ARCHITECTURE.md#14-repository-layout).

### Step 2 — Docker Compose infra (Postgres+PostGIS+Timescale, Redis)

**Goal:** databases and cache boot locally.
**Tasks:** `infra/docker-compose.yml` with services `db` (image `timescale/timescaledb-ha:pg16` which bundles PostGIS+Timescale) and `redis`; named volumes; healthchecks; `.env` wiring.
**Commands:**

```bash
docker compose -f infra/docker-compose.yml up -d db redis
docker compose -f infra/docker-compose.yml exec db psql -U careplus -c "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

**✅ Acceptance:** both extensions report installed; `redis-cli ping` → `PONG`.

### Step 3 — Django backend skeleton (Dockerized, Python 3.11)

**Goal:** Django + DRF project builds and runs in Docker.
**Tasks:** `backend/Dockerfile` (python:3.11-slim + GDAL for GeoDjango), `backend/requirements.txt` (Django 4.2, DRF, channels, daphne/uvicorn, psycopg, redis, celery, django-environ, djangorestframework-simplejwt, drf-spectacular), `django-admin startproject careplus`, settings split (`base/dev/prod`), `apps/` package.
**Commands:**

```bash
docker compose -f infra/docker-compose.yml up -d --build backend
docker compose -f infra/docker-compose.yml exec backend python manage.py migrate
```

**✅ Acceptance:** `GET /api/v1/health/` → `{"status":"ok","db":"ok","redis":"ok"}`.

### Step 4 — ASGI + Channels + Celery wiring

**Goal:** realtime + async task rails in place (no features yet).
**Tasks:** `asgi.py` with `ProtocolTypeRouter`, Redis channel layer, a `ping` WebSocket consumer; Celery app + Redis broker; a `debug_task`.
**Commands:**

```bash
docker compose -f infra/docker-compose.yml up -d worker
```

**✅ Acceptance:** WS `ws/ping` echoes; Celery `debug_task` runs and logs.

### Step 5 — API docs + CI + code quality

**Goal:** contracts visible, quality gates on.
**Tasks:** drf-spectacular schema at `/api/schema` + Swagger UI; `ruff` + `black` (Python), `eslint` + `prettier` (JS); pre-commit; GitHub Actions running lint + tests + `docker build`.
**✅ Acceptance:** CI green on a PR; `/api/docs` renders.

---

## M1 · Auth & Consent

### Step 6 — Custom user + JWT auth

**Goal:** register/login with roles.
**Tasks:** `accounts` app, custom `User` (email login, `role` = patient/caregiver/admin/auditor), SimpleJWT endpoints, RBAC permission classes.
**✅ Acceptance:** register → obtain JWT → access role-guarded endpoint; wrong role → 403.

### Step 7 — Consent engine (PDPA/GDPR gate)

**Goal:** block AI processing without consent.
**Tasks:** `ConsentLog` model + `/api/v1/consent`; DRF permission `HasAIConsent` used by the voice pipeline.
**✅ Acceptance:** voice endpoint returns 451/403 until consent granted, then passes.

### Step 8 — Immutable audit trail

**Goal:** HIPAA/PDPA access logging.
**Tasks:** append-only `AuditLog`; Celery task to write `{actor, action, ts, ip}`; DB role lacks UPDATE/DELETE on the table.
**✅ Acceptance:** viewing patient health data writes exactly one immutable audit row.

---

## M2 · Web shell + Neural Core

### Step 9 — Shared packages + web app bootstrap

**Goal:** monorepo packages + Vite React app run.
**Tasks:** `packages/ui-tokens` (Aurora Neural tokens), `packages/core` (i18n, FSM types), `packages/api-client` (typed fetch + Zod), `apps/web` (Vite + React + TS + Tailwind + router).
**Commands:**

```bash
pnpm install && pnpm --filter web dev
```

**✅ Acceptance:** themed blank app loads; tokens imported from `ui-tokens`.

### Step 10 — Auth screens + API client wiring

**Goal:** login/register on web against Django.
**✅ Acceptance:** login stores JWT, authed route reachable, logout clears session.

### Step 11 — Neural Core visual (audio-reactive brain)

**Goal:** the signature visual on web.
**Tasks:** `neural-core/` R3F scene — neural mesh + synapse lines, emissive shader, Bloom postprocessing, `frameloop="demand"`; Web Audio `AnalyserNode` → amplitude drives scale/glow.
**✅ Acceptance:** brain pulses to mic input at ~60 fps; idle uses ~0% GPU (render-on-demand).

### Step 12 — Assistant FSM + Goal Ring + realtime feedback shell

**Goal:** the state machine and UI scaffolding.
**Tasks:** Zustand FSM (IDLE→…→EMERGENCY), Goal Ring component, transcript + entity-chip components (wired to mock data), color-per-state.
**✅ Acceptance:** manually stepping states drives brain color + Goal Ring; reduced-motion respected.

---

## M3 · Voice → Intent

### Step 13 — Mic capture + live transcript (Web Speech)

**✅ Acceptance:** speaking shows streaming interim transcript; silence → THINKING.

### Step 14 — Gemini structured-output intent extraction (backend)

**Goal:** text → strict JSON.
**Tasks:** `voice` app, `/api/v1/voice/intent`, Gemini 1.5 Flash client with `response_mime_type=application/json` + schema; server-side Zod-equivalent validation; consent-gated; persist intent.
**✅ Acceptance:** `"මට දියවැඩියාව තියෙනවා…"` → validated `{condition, language, care_level}` stored.

### Step 15 — Entity chips + Goal Ring fill (end-to-end)

**✅ Acceptance:** captured fields pop chips + fill the ring; missing field → CLARIFYING re-prompt.

---

## M4 · VEHMF v1 + Match UX

### Step 16 — Domain models + seed data

**Tasks:** `CaregiverProfile` (PostGIS `POINT`, certifications, languages, `trust_score`, `embedding`), `PatientProfile`; seed script with realistic Sri Lanka geodata.
**✅ Acceptance:** seed loads N caregivers with valid geometries.

### Step 17 — Embeddings + FAISS index build

**Tasks:** `ml/build_index.py` using `multilingual-e5-base`; L2-normalized vectors; `IndexFlatIP`; load into memory in the matching module.
**✅ Acceptance:** index build reproducible; nearest-neighbor query returns sensible caregivers.

### Step 18 — AHP weights

**Tasks:** `ml/ahp.py` principal-eigenvector solver from a survey matrix; export `[α, β, γ, δ]`; consistency-ratio check.
**✅ Acceptance:** weights sum to 1, CR < 0.1, loaded at startup.

### Step 19 — VEHMF engine (CBF + Geo + Trust + fusion + XAI)

**Tasks:** implement `VEHMFEngine.predict` per [ARCHITECTURE.md §7](ARCHITECTURE.md#7-the-vehmf-engine-code-level-design); PostGIS travel-time scoring; trust scoring; normalization; XAI text.
**✅ Acceptance:** `/api/v1/match` returns ranked list + breakdown + explanation; unit tests on fusion math.

### Step 20 — Match over WebSocket + result UX

**Tasks:** `ws/match/{patient}` push; result cards with score breakdown + XAI + `latency_ms` badge.
**✅ Acceptance:** voice → ranked, explained results in UI, **p95 < 800 ms** on seed data.

---

## M5 · Personalization

### Step 21 — CF training (offline)

**Tasks:** interaction/ratings model; `ml/train_cf.py` (`implicit` ALS) as nightly Celery beat; artifact versioning.
**✅ Acceptance:** model trains on seed interactions; produces per-user scores.

### Step 22 — Blend CF into fusion

**✅ Acceptance:** fusion uses all four factors; A/B toggle; offline ranking metric improves vs CBF-only.

---

## M6 · Health monitoring

### Step 23 — Timescale hypertable + ingest API/MQTT

**✅ Acceptance:** `HEALTH_METRIC` hypertable ingests simulated stream; time-window aggregate query fast.

### Step 24 — Anomaly daemon (threshold → rules → optional LSTM)

**✅ Acceptance:** simulated hypoglycemia trend raises `health_critical`.

### Step 25 — Dynamic re-weight + emergency re-match

**✅ Acceptance:** emergency shifts weights (α↑, γ↓), bypasses normal ranking, picks nearest certified nurse.

### Step 26 — Alerts UX + push

**✅ Acceptance:** EMERGENCY state (rose brain) + FCM/web push fires on anomaly.

---

## M7 · Scheduling

### Step 27 — Shift model + calendar UX

### Step 28 — Redlock booking + overlap check

**✅ Acceptance:** concurrent booking test → exactly one success, no double-book.

### Step 29 — Conflict fallback re-match

**✅ Acceptance:** loser gets next-best caregiver automatically.

---

## M8 · Mobile app (Expo RN)

### Step 30 — Expo app bootstrap + shared packages

### Step 31 — Auth + navigation (expo-router)

### Step 32 — Neural Core on Skia + Reanimated (audio-reactive)

### Step 33 — Voice → intent → match parity (patient flow)

### Step 34 — Push notifications (FCM/APNs) + health alerts

**✅ Acceptance (M8):** Android + iOS builds run the full patient voice-to-match + alerts flow at 60 fps.

---

## M9 · Compliance & hardening

### Step 35 — `pgcrypto` AES-256 on health/intent columns

### Step 36 — Right-to-erasure (DB purge + FAISS eviction) + data export

### Step 37 — TLS 1.3, security headers, rate limits, load & concurrency tests

**✅ Acceptance:** compliance checklist passes; load test meets latency targets.

---

## M10 · Ship

### Step 38 — CI/CD pipeline (build, test, push images)

### Step 39 — Deploy to VM (Compose/prod) + observability (logs, metrics, Sentry)

### Step 40 — Mobile store submissions (Play Store + App Store)

**✅ Acceptance:** production URL live, monitored; apps in review.

---

## Working agreement (how we run each step)

1. **Branch** off up-to-date `main` as `feat/stepN-<slug>` (or `fix/` / `chore/`).
2. State the step goal + what will change.
3. Implement in focused chunks; a branch may have **many commits**.
4. Run the step's acceptance check and show the result.
5. **Push** the branch after development (and at other necessary times).
6. When the branch is complete (or when needed): open a PR → **merge** into `main`.
7. Pull `main`, start the next step on a **new** branch.

Canonical rules: `.cursor/rules/git-workflow.mdc` (always applied).

> **Next up: Step 15** — entity chips + Goal Ring fill end-to-end (`feat/step15-intent-ui`).
