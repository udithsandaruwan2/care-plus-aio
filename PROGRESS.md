# Care Plus — Progress Log

> **Purpose:** running record of _what's done_ and _what's next_, so work can resume
> from any device. Committed to git (syncs across machines). Updated **feature by feature**.
> Full plan: [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) ·
> Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) ·
> Frontend: [docs/FRONTEND.md](docs/FRONTEND.md)

_Last updated: 2026-07-18 — Neural Core glow fixed (neuron cloud, no square fill). Next: Step 16 (domain models + seed data)._

---

## Git workflow (cross-device)

| Rule | Detail |
|------|--------|
| **Branch** | One branch per feature/step (`feat/stepN-<slug>`, `fix/…`, `chore/…`) off `main` |
| **Commits** | Many focused commits per branch OK |
| **Push** | Always push after development (and when switching devices / end of session) |
| **Merge** | When the branch is complete (or when necessary): PR → merge into `main` |
| **Next feature** | New branch from updated `main` — never pile features on one branch |

Rules file: `.cursor/rules/git-workflow.mdc`.

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
- ✅ **Step 3** — Dockerized Django+DRF skeleton; `/api/v1/health/` green; DRF Browsable API for exploration. commit `322f99a`
- ✅ **Step 4** — Channels `ws/ping` echo consumer + Celery worker + `debug_task` (both verified).
- ✅ **Step 5** — Quality gates: Ruff+Black (py), Prettier+ESLint (js), pre-commit, GitHub Actions CI. **M0 complete.**

### M1 · Auth & Consent

- ✅ **Step 6** — Custom `User` (email login + role) + JWT + RBAC. Branch `feat/step6-auth-jwt-rbac`.
- ✅ **Step 7** — Consent engine: append-only `ConsentLog` + `/api/v1/consent` + `HasAIConsent` gate (451). Branch `feat/step7-consent-engine`.
- ✅ **Step 8** — Immutable audit trail: `AuditLog` + Celery writer + Postgres trigger; demo `view_health`. Branch `feat/step8-audit-trail`. **M1 complete.**

### M2 · Web shell + Neural Core

- ✅ **Step 9** — Shared packages (`ui-tokens`, `core`, `api-client`) + Vite React web shell (Aurora Neural). Branch `feat/step9-web-shell`.
- ✅ **Step 10** — Login/register screens, JWT session, protected home + logout. Branch `feat/step10-web-auth`.
- ✅ **Step 11** — Neural Core: R3F icosahedron mesh + synapses + Bloom; mic amplitude; `frameloop=demand`. Branch `feat/step11-neural-core`.
- ✅ **Step 12** — Assistant FSM (Zustand) + Goal Ring + entity chips + transcript + reduced-motion; dev state stepper. Branch `feat/step12-assistant-fsm`.
- 🔜 Step 13 — Mic capture + live transcript (Web Speech)

### M3 · Voice → Intent

- ✅ **Step 13** — Web Speech mic capture + live streaming transcript; lang toggle (si/ta/en); silence → THINKING. Branch `feat/step13-web-speech`.
- ✅ **Step 14** — Backend `voice/intent` extraction (Gemini + deterministic stub), consent-gated (451), persists `VoiceIntent`; audited. Branch `feat/step14-voice-intent`.
- ✅ **Step 15** — End-to-end: transcript → `POST /voice/intent/` → chips pop + Goal Ring fills; missing field → CLARIFYING re-prompt; 451 → one-tap "Enable AI processing" consent + retry. Branch `feat/step15-intent-ui`. **M3 complete.**

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

- **Fix** — Neural Core no longer lights up as a solid square: removed opaque icosahedron fill + full-frame Bloom (they painted the canvas rect). Replaced with a volume-filled neuron/synapse cloud (additive points + links), circular clip on the Goal Ring child slot, transparent GL clear. Branch `fix/neural-core-natural-glow`.
- **Step 15** — Web voice loop end-to-end: `api-client` gains `voiceIntent` + `getConsent`/`setConsent` (+ Zod `VoiceIntent`/`ConsentState` schemas); `useIntentExtraction` hook posts the finalized transcript, merges the structured draft into the assistant store (`setIntent`), and drives FSM → SPEAKING (complete) or CLARIFYING (`nextMissingField` re-prompt). HomePage lights entity chips + Goal Ring, shows the clarify prompt, and renders a consent banner (one-tap "Enable AI processing" → retry) when the gate returns 451. Typecheck + web build green. Branch `feat/step15-intent-ui`.
- **Step 14** — `apps.voice`: `VoiceIntent` model + `POST /api/v1/voice/intent/` (`IsAuthenticated` + `HasAIConsent`, 451 without consent), pluggable extractor (`gemini` Structured Output + deterministic `stub` for dev/tests), Sinhala/Tamil/English detection, writes audit row, read-only admin, history endpoint. 16 tests green. Branch `feat/step14-voice-intent`.
- **Step 13** — `useSpeechRecognition` (Web Speech API): streaming interim + final transcript into the store, language toggle (si-LK/ta-LK/en-US), silence/stop → THINKING; graceful unsupported-browser note. Branch `feat/step13-web-speech`.
- **Step 12** — Zustand assistant FSM (`TRANSITIONS`/`STATE_COPY`/`nextMissingField` in core); segmented Goal Ring per intent field; color-coded entity chips; live transcript component; `prefers-reduced-motion` static Neural Core; dev state stepper. Branch `feat/step12-assistant-fsm`.
- **Step 11** — Neural Core on home: `useMicAmplitude` (AnalyserNode), R3F mesh + synapse lines + Bloom, `frameloop="demand"` (idle static), Tap to speak toggles LISTENING. Lazy-loaded Three.js chunk. Branch `feat/step11-neural-core`.
- **Step 10** — Web auth: `/login` + `/register`, JWT in localStorage, `AuthProvider` + `RequireAuth`, protected `/` shows `/me`, logout clears session. `api-client` gains `register` + Zod `TokenPair` parse. CORS verified for `:5173`. Branch `feat/step10-web-auth`.
- **Step 9** — Monorepo frontend: `@care-plus/ui-tokens` (Aurora Neural), `@care-plus/core` (FSM + i18n stub), `@care-plus/api-client` (Zod + fetch), `apps/web` Vite/React/Tailwind themed shell with live health probe. `pnpm` install + typecheck + build green. Branch `feat/step9-web-shell`.
- **Step 8** — Append-only `AuditLog` (`actor`, `action`, `ts`, `ip`, target, metadata); Celery `write_audit_log` + `record_audit`; Postgres BEFORE UPDATE/DELETE trigger; `GET /audit/demo-view-health/` writes one `view_health` row; `GET /audit/` for admin/auditor; read-only admin. Tests green. Branch `feat/step8-audit-trail`. **M1 complete.**
- **Fix** — WhiteNoise + `collectstatic` entrypoint so Django admin / DRF Browsable API CSS works under uvicorn. Branch `fix/backend-static-whitenoise`.
- **Workflow** — Branch → many commits → **always push** after development → PR/merge when complete. Documented in `.cursor/rules/git-workflow.mdc`, `PROGRESS.md`, `DEVELOPMENT_PLAN.md`.
- **Chore** — Dropped Swagger/`drf-spectacular`; API exploration/testing now uses DRF's built-in **Browsable API** (dev) with `api-auth/` login. Removed `/api/schema` + `/api/docs`. Branch `chore/drf-browsable-api`.
- **Step 7** — `accounts` consent engine: append-only `ConsentLog` (`user`, `scope`, `granted`, `ts`) with `is_granted`/`current_state` helpers; `ConsentScope` = `ai_processing`/`health_monitoring`/`data_sharing`; `POST/GET /api/v1/consent/`; `HasAIConsent` DRF permission raising **451** when consent is missing; `/api/v1/consent/gate-check/` demo endpoint (401→451→200). Read-only admin. Tests cover ledger append-only + gate. Branch `feat/step7-consent-engine`.
- **Step 6** — `accounts` app: custom email User + `role` (patient/caregiver/admin/auditor), SimpleJWT (`/auth/token`, `/refresh`), `/auth/register`, `/auth/me`, RBAC `RolePermission` + `/auth/admin-only`. DB recreated for custom user. Verified: 201/200/403/200/401.
- **Workflow** — adopted one-branch-per-feature (`feat/stepN-<slug>`).
- **Step 5** — Ruff+Black (`backend/pyproject.toml`), Prettier + flat ESLint config, `.pre-commit-config.yaml`, GitHub Actions CI (backend lint · prettier · docker build). Lint/format verified clean.
- **Step 4** — ASGI `ProtocolTypeRouter` (HTTP+WebSocket); `ws/ping` echo consumer; Celery app on Redis + `debug_task`; `worker` service in Compose.
- **Step 3** — Django 4.2 + DRF + GeoDjango skeleton, split settings, health endpoint (DB+Redis), DRF Browsable API; backend service in Compose. `322f99a`
- **Step 2** — `infra/docker-compose.yml` (TimescaleDB-HA + Redis) + init SQL (postgis/timescaledb/pgcrypto); host DB port → 5433.
- **Step 1** — Monorepo skeleton, workspace config, `.env.example`. `ced6d2d`
- **Docs** — ARCHITECTURE.md, FRONTEND.md, DEVELOPMENT_PLAN.md; connected `origin/main`.
