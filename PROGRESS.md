# Care Plus — Progress Log

> **Purpose:** running record of _what's done_ and _what's next_, so work can resume
> from any device. Committed to git (syncs across machines). Updated **feature by feature**.  
> Full plan: [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) **v0.3 (~80 steps, complete)** ·  
> Engine plan: [docs/DEVELOPMENT_PLAN_V2.md](docs/DEVELOPMENT_PLAN_V2.md) **v0.4 (Steps 76–106, active)** ·  
> Vision (Old→New): [docs/PRODUCT_VISION.md](docs/PRODUCT_VISION.md) ·  
> Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) ·  
> Dialogue AI: [docs/DIALOGUE_POLICY.md](docs/DIALOGUE_POLICY.md) ·  
> Frontend: [docs/FRONTEND.md](docs/FRONTEND.md)

_Last updated: 2026-08-21 — Step 95 offline outbox._

---

## Git workflow (cross-device)

| Rule             | Detail                                                                                              |
| ---------------- | --------------------------------------------------------------------------------------------------- |
| **Author**       | Always **Udith Sandaruwan** `<developer.udithsandaruwan@gmail.com>` — never `Care Plus Dev` / agent |
| **How**          | Terminal only: `git add` → `git -c user.name=… -c user.email=… commit` → `git push` → `gh pr …`     |
| **Branch**       | One branch per feature/step (`feat/stepN-<slug>`, `fix/…`, `chore/…`) off `main`                    |
| **Commits**      | Many focused commits per branch OK                                                                  |
| **Push**         | Always push after development (and when switching devices / end of session)                         |
| **Merge**        | When the branch is complete (or when necessary): PR → merge into `main`                             |
| **Next feature** | New branch from updated `main` — never pile features on one branch                                  |

Rules file: `.cursor/rules/git-workflow.mdc` (includes identity + terminal commit recipe).

---

## How to resume on a new device

```bash
git clone https://github.com/udithsandaruwan2/care-plus-aio.git "Care Plus"
cd "Care Plus"
cp .env.example .env                      # fill in secrets (GEMINI_API_KEY, etc.)
docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml exec -T backend python manage.py migrate --noinput
docker compose -f infra/docker-compose.yml exec -T backend python manage.py seed_demo
curl -fsS http://localhost:8000/api/v1/health/   # expect {"status":"ok","db":"ok","redis":"ok"}
pnpm --filter @care-plus/web dev --host 127.0.0.1 --port 5173
```

Demo logins (after `seed_demo`, password **`CarePlus!demo`**): `demo.patient@careplus.local` (active care), `demo.caregiver@careplus.local`, `demo.admin@careplus.local`. Dev login page lists click-to-fill accounts.

Notes:

- Backend runs in Docker on **Python 3.11** (host Python version irrelevant).
- Host DB port is **5433** (container internal 5432) to avoid clashing with a local Postgres.
- Local reference only: `Old Care Plus/` (gitignored) — old Lumora/Care Plus HND app for product shape.
- Requires Docker + ~5–10 GB free disk.
- CI/CD: [docs/ops/ci-cd.md](docs/ops/ci-cd.md)
- TLS proxy: [docs/ops/tls-proxy.md](docs/ops/tls-proxy.md)
- Deploy VM + observability: [docs/ops/deploy.md](docs/ops/deploy.md)
- Mobile (Expo Go / APK): [docs/ops/mobile-expo.md](docs/ops/mobile-expo.md)
- Launch checklist: [docs/ops/launch-checklist.md](docs/ops/launch-checklist.md)

---

## Decisions locked (lean profile)

See DEVELOPMENT_PLAN §0. Highlights: Web Speech + whisper fallback · VEHMF matching ·
TimescaleDB · e5-base embeddings · Medical Light UI · Care Plus brand · canonical medical vocab ·
real PaymentIntent (mock provider in dev).

---

## Status board (v0.2)

Legend: ✅ done · 🔜 next · ⬜ pending · ░ planned (detail in DEVELOPMENT_PLAN)

### Done foundations

- ✅ **M0** Steps 1–5 — Foundations
- ✅ **M1** Steps 6–8 — Auth, consent, audit
- ✅ **M2** Steps 9–12 — Web shell + Neural Core
- ✅ **M3** Steps 13–15 — Voice → intent → chips/ring
- ✅ **M4** Step 16 — Domain profiles + Sri Lanka seed
- ✅ **UI Medical Light** — Teal/white tokens, PublicLayout + Hub sidebar (`/hub`), Serah CSS orb HUD, restyled public/hub/mobile chrome. Branch `feat/ui-medical-light-redesign`.
- ✅ **Serah match progress + companion** — VEHMF search shows a progress bar and skeleton cards; empty/ambient audio stays silent; goodbye sleeps until “Hey Serah”; hub pages keep a live bottom-right Serah bubble. Branch `feat/serah-match-progress-dock`.
- ✅ **Showcase synthetic data** — `seed_demo` loads vocab, catalog, 30 SL caregivers, and every situation (pending/rejected/cancelled/expired hire, paid care, failed pay, messages, records, vitals/emergency, reviews, leads, admin). Branch `feat/showcase-synthetic-data`.
- ✅ **Serah search stage** — caregiver search keeps the matching UI on (orb slides left, progress + thinking copy + skeleton cards) even if chat promised VEHMF; backend salvage runs the real match. Branch `feat/serah-match-search-stage`.
- ✅ **Sinhala/Tamil Serah voice** — chat replies in සිංහල/தமிழ் use server TTS (Edge/Gemini/espeak); browsers have no those voices so speechSynthesis was silent. Branch `fix/sinhala-serah-voice`.
- ✅ **Start → search UI** — “start” / “let’s get that search going” now runs VEHMF and shows the matching panel even without a condition chip. Branch `fix/serah-start-shows-search`.
- ✅ **Serah keep results layout** — talking during search no longer hides the loading/results panel; orb stays pinned on the left while caregiver cards scroll on the right. Branch `fix/serah-keep-results-layout`.
- ✅ **Serah neural stage field** — unclipped 3D connectome (hubs, synapses, traveling pulses) fills Serah Core; public landing uses the same mesh in a rounded well. Branch `feat/serah-neural-stage-field`.
- ✅ **Public neural hero, no box** — landing page graph is transparent on white (no dark rounded card). Branch `fix/public-neural-well-box`.
- ✅ **Serah stage composition** — removed the gray well smear; Goal lives in the HUD; copy sits under the graph instead of on it. Branch `fix/serah-stage-composition`.
- ✅ **Serah match rail** — caregiver cards sit in a bordered scrolling rail; Speak keeps existing matches (New request still clears). Branch `fix/serah-match-rail`.
- ✅ **Serah search fit + voice** — matching stage fills the viewport (graph | rail, no page scroll); Serah narrates finding vs results-ready. Branch `fix/serah-match-rail`.
- ✅ **Serah compact match orb** — after recommendations, the neural mesh shrinks to a left dock; cards take the remaining width without overflowing. Branch `fix/serah-compact-match-orb`.
- ✅ **Serah half split** — match stage is 50/50 orb+chat | caregiver cards. Branch `fix/serah-half-split`.

### Active track — research match loop

- ✅ **Step 17** — Embeddings + FAISS `IndexFlatIP` (hash embedder default; e5 optional); `build_caregiver_index` / `query_caregiver_index`; `POST /match/cbf/`. Branch `feat/step17-embeddings-faiss`.
- ✅ **Step 18** — AHP principal-eigenvector weights `[α,β,γ,δ]` (CR < 0.1); `config/ahp_weights.json`; env emergency override; `GET /match/weights/`. Branch `feat/step18-ahp-weights`.
- ✅ **Step 19** — `VEHMFEngine` (CBF+CF-stub+Geo+Trust+XAI); `MatchRun`/`MatchResult`; consent-gated `POST /api/v1/match/`. Branch `feat/step19-vehmf-engine`.
- ✅ **Step 20** — JWT `ws/match/{id}/` + push; MatchResultCards; SPEAKING→MATCHING→RESULTS. Branch `feat/step20-match-ux`.
- ✅ **Step 15b** — Canonical `ConditionTerm` vocab (≥37); `GET /vocab/conditions/`; stub maps ඩෙංගු→`dengue`. Branch `feat/step15b-medical-vocab`.
- ✅ **Step 20b** — Caregiver search/filter/geo API + pagination (`city`, `is_available`). Branch `feat/step20b-caregiver-search`.
- ✅ **Step 20c** — `/caregivers` browse UI (chips + Leaflet map). Branch `feat/step20c-browse-ui`.
- ✅ **Step 20d** — Caregiver public detail `/caregivers/:id` + audited API. Branch `feat/step20d-caregiver-detail`.
- ✅ **Step 20e** — Availability flag + soft presence (`GET/PATCH /caregivers/me/`, match hides unavailable, `/presence`). Branch `feat/step20e-availability`.
- ✅ **Step 15g** — DialogueSession memory + New request clear. Branch `feat/step15g-session-memory`.
- ✅ **Step 15i** — Post-match refine deltas → VEHMF filters + rank-change UI. Branch `feat/step15i-post-match-refine`.
- ✅ **Step 15j** — Dialogue AI policy (stub/gemini chat, VEHMF-only match, rate limit). Branch `feat/step15j-dialogue-policy`.
- ✅ **Step 15h** — Unified loop: chat bubbles, CHAT_REPLY FSM, mic re-arm. Branch `feat/step15h-conversation-loop`.
- ✅ **Step 21** — `Interaction` log (view/request/accept/complete/rate); implicit ALS `train_cf` + `seed_interactions`; Celery beat nightly; versioned `ml/artifacts/cf/`. Branch `feat/step21-cf-interactions`.
- ✅ **Step 22** — ALS CF blended into VEHMF; `CF_ENABLED` flag zeroes β; NDCG/MAP tests; `cf_enabled`/`cf_version` on match payloads. Branch `feat/step22-cf-blend`.
- ✅ **Step 22b** — Patient onboarding wizard; `GET/PATCH /patients/me/`; completion % gates request care. Branch `feat/step22b-patient-onboarding`.
- ✅ **Step 22c** — Caregiver onboarding wizard; `GET/PATCH /caregivers/me/`; inactive until ≥80% + approval. Branch `feat/step22c-caregiver-onboarding`.
- ✅ **Step 22d** — Profile photo + cert document uploads; signed download URLs; virus-scan stub. Branch `feat/step22d-profile-media`.
- ✅ **Step 22f** — Optional email OTP (`OTP_ENABLED`); JWT `otp_verified`; hire/pay/records gated. Branch `feat/step22f-email-otp`.
- ✅ **Step 23** — `CareRequest` model + API; patient request from match/profile; caregiver inbox; expiry job. Branch `feat/step23-care-request`.
- ✅ **M0–M17** product steps are in code. **Step 74** store submissions remain deferred (Expo Go).

### Expanded product tracks (from Old Care Plus)

| Milestone                             | Steps   | Status                                                          |
| ------------------------------------- | ------- | --------------------------------------------------------------- |
| **M3b** Medical vocab + Serah chat    | 15b–15e | ✅ (vocab + `/voice/turn/` chat/TTS)                            |
| **M3c** Conversational dialogue loop  | 15f–15j | ✅ done                                                         |
| **M4b** Marketplace browse/map/detail | 20b–20e | ✅ done                                                         |
| **M5** CF personalization             | 21–22   | ✅ done                                                         |
| **M5b** Rich onboarding / OTP         | 22b–22f | ✅ done                                                         |
| **M6** Hire lifecycle (`CareRequest`) | 23–28   | ✅ done                                                         |
| **M7** Catalog + checkout + payments  | 29–33   | ✅ done                                                         |
| **M8** Medical records                | 34–37   | ✅ done                                                         |
| **M9** Messaging + notifications      | 38–41   | ✅ done                                                         |
| **M10** Reviews → trust               | 42–44   | ✅ done                                                         |
| **M11** Health monitoring + emergency | 45–49   | ✅ done                                                         |
| **M12** Scheduling + Redlock          | 50–53   | ✅ done                                                         |
| **M13** Admin console                 | 54–58   | ✅ done                                                         |
| **M14** i18n + a11y                   | 59–61   | ✅ done                                                         |
| **M15** Mobile Expo                   | 62–67   | ✅ done                                                         |
| **M16** Compliance                    | 68–71   | ✅ done                                                         |
| **M17** Ship                          | 72–75   | 72–73 ✅ · **74 deferred** (Expo Go, no store accounts) · 75 ✅ |

**Progress:** numbered plan implemented. Remaining ops choice: enable `OTP_ENABLED` in production if desired; Play/App Store when accounts exist.

---

## Status board (v0.4 — engine & experience)

Plan: [docs/DEVELOPMENT_PLAN_V2.md](docs/DEVELOPMENT_PLAN_V2.md). One branch per step, `feat/stepN-<slug>`.

| Milestone                                | Steps   | Status | Outcome                                                              |
| ---------------------------------------- | ------- | ------ | -------------------------------------------------------------------- |
| **M18** Signal & telemetry foundations   | 76–79   | 76–79 ✅ | Outcomes logged, stages timed, AI decisions audited and reproducible |
| **M19** Client efficiency                | 80–82   | 80–82 ✅ | Smaller first load, calmer render loop, network-tolerant boot        |
| **M20** Conversation feel                | 83–87   | 83–87 ✅ | Streaming turns, interruptible speech, recoverable failures          |
| **M21** Model lifecycle                  | 88–92   | 88–92 ✅ | Registry, auto index rebuild, replay eval, gated promotion           |
| **M22** Offline & local intelligence     | 93–98   | 93–95 ✅ | Installable PWA, cached reads, queued writes, local slot model       |
| **M23** Adaptive ranking                 | 99–103  | ⬜      | Cold-start clustering, exploration, learned weights, A/B, fairness   |
| **M24** History surface & retention      | 104–106 | ⬜      | User-visible trail, complete export, retention policy                |

**Why this order:** M18 captures the outcome signals that CF actually trains on. Step 76 now
writes COMPLETE / RATE / REJECT; remaining M18 steps make those decisions timed and auditable.
M21 and M23 stay after the rest of M18.

**Next:** Step 96 — Local slot classifier, branch `feat/step96-slot-classifier`.

---

## What works today (user-facing)

- Register / login (JWT), optional email OTP (`OTP_ENABLED`), consent gate, Neural Core voice UI
- Speak or chat (si/ta/en) → Serah via `/voice/turn/` → chips + Goal Ring; match/refine/chat router
- Seeded caregivers + **VEHMF `POST /match/`** (ranked + breakdown + XAI) + browse/map/detail
- Onboarding, profile photos, care requests, checkout/pay, records, messaging, schedule, admin
- Web + Expo Go (SDK 54). Store listings deferred until Play/App Store accounts exist.

---

## Changelog (newest first)

- **Step 95** — Queued writes: IndexedDB outbox + Background Sync, pending UI; server idempotency for care requests, messages, mock payment confirm. Branch `feat/step95-offline-outbox`.

- **Step 94** — Cached reads: IndexedDB query layer for profiles, browse, caregiver detail, messages, last match; fresh mounts skip refetch; offline shows Cached badge. Branch `feat/step94-offline-reads`.

- **Step 93** — Installable PWA: vite-plugin-pwa Workbox shell + fonts, push handlers preserved, manifest/icons, `/offline` + `offline.html`. Branch `feat/step93-pwa-shell`.

- **Step 92** — Negative CF signals: confidence-weighted ALS with REJECT (hard) and VIEW-only (weak) negatives; beats positives-only ALS on NDCG@5 / recall@10 in suite. **M21 complete.** Branch `feat/step92-negative-signals`.

- **Step 91** — Gated CF promotion: holdout NDCG gate before `current.json` / ModelVersion activate; `promote_model --force` escape hatch; shuffled candidates rejected. Branch `feat/step91-gated-promotion`.

- **Step 90** — Replay eval harness: `eval_ranking` on causal holdout MatchRuns; NDCG@5, MAP, recall@10, precision@5, coverage, exposure Gini; reproducible. Branch `feat/step90-eval-harness`.

- **Step 89** — Automatic FAISS refresh: Celery re-embed on caregiver me PATCH, hourly stale no-op rebuild, dirty flag after eviction. Branch `feat/step89-index-refresh`.

- **Step 88** — Model registry: `ModelVersion` for cf/faiss/slot_classifier, one active per kind, CF/FAISS writers + MatchRun FKs, read-only Django admin. Branch `feat/step88-model-registry`.

- **Step 87** — Reply render + card density: progressive Serah bubbles, collapsed VEHMF disclosure, #1-vs-#2 comparative line, orb alt text + state live region. Branch `feat/step87-reply-render`. **M20 complete.**

- **Step 86** — Recoverable turns: keep transcript on failure, typed error copy (network/timeout/429/451), inline retry, single auto-replay when back online. Branch `feat/step86-turn-recovery`.

- **Step 85** — Barge-in: mic analyser watches energy during TTS; sustained speech stops Serah and starts a new listen; ASR paused during playback to avoid echo self-triggers. Branch `feat/step85-barge-in`.

- **Step 84** — TTS decouple: `first_text_ms` before synthesis; uncached audio deferred to WS/`POST /voice/tts/`; Redis phrase cache with logged hit rate. Branch `feat/step84-tts-decouple`.

- **Step 83** — Streaming voice turn: `process_turn` emits `turn.*` stages on `ws/match/`; client fills transcript/chips/reply progressively; HTTP remains fallback with request_id dedupe. Branch `feat/step83-streaming-turn`.

- **Step 82** — Network-tolerant client: keep last known user on transport errors (`sessionStale`), 30s timeouts + GET retries, offline/degraded banner in AppShell. Branch `feat/step82-network-tolerance`.

- **Step 81** — Neural-core render budget: ~30 fps idle, skip unchanged 104-neuron matrices, IntersectionObserver pause, mic amplitude via ref + 15 Hz React cap. Branch `feat/step81-render-budget`.

- **Step 80** — Web first-load: lazy routes, recharts/leaflet/three chunks, self-hosted fonts, CI entry budget 450 KB (measured ~196 KB). Branch `feat/step80-bundle-split`.

- **Step 79** — MatchRun provenance: CF/index versions, filters, voice intent, `request_id`; `replay_match`; export includes per-caregiver factor scores. Branch `feat/step79-matchrun-provenance`.

- **Step 78** — AI decision audit: `RUN_MATCH` from every MatchRun, `GRANT_CONSENT`/`REVOKE_CONSENT` from consent POST, `LOGIN` on JWT issue; `AuditLog.request_id` joins HTTP logs. Branch `feat/step78-ai-audit`.

- **Step 77** — Voice turn telemetry: `timings` on `/voice/turn/` (ASR/intent/route/match/chat/TTS), JSON logs with `request_id`, admin `turn_latency` p95. VEHMF &lt;800 ms is engine-only. Branch `feat/step77-turn-telemetry`.

- **Step 76** — Outcome interactions: COMPLETE on relationship end, RATE on review submit, REJECT on declined hire (weight −1.0); idempotent `backfill_interactions`; ALS skips non-positive weights. Branch `feat/step76-outcome-interactions`.

- **Docs v0.4** — Engine plan Steps 76–106 (M18–M24): telemetry, streaming turns, offline + local model, history trail, self-improving ranking. Branch `docs/engine-development-plan-v04`.

- **Demo gateways** — Stripe-lookalike checkout (test card `4242…`, no real charge); email OTP dummy code `123456` with no outbound mail (`OTP_DUMMY`). Branch `feat/dummy-stripe-otp`.

- **Docs** — Status board matches shipped code (M0–M17); README no longer says pre-development. Branch `chore/progress-board-complete`.

- **Step 22f** — Optional email OTP 2FA: request/verify endpoints, `otp_verified` JWT claim, hire/pay/records gated when `OTP_ENABLED=true`. Web `/otp` + Expo verify screen. Branch `feat/step22f-email-otp`.

- **Step 22d** — Profile photos (`ImageField`) + caregiver certification files; signed download tokens (no public bucket); virus-scan stub; Account + caregiver detail UI. Branch `feat/step22d-profile-media`.

- **Step 75** — Launch checklist: public PDPA notice (`/privacy`), support email, Postgres backup script + runbook, Expo Go (store submissions deferred). Branch `feat/step75-launch-checklist`.

- **Step 74** — Deferred: no Play/App Store accounts. Testers use Expo Go SDK 54; optional EAS preview APK later. See `docs/ops/mobile-expo.md`.

- **Step 73** — Deploy VM + observability: Caddy TLS 1.3 in prod Compose, `infra/scripts/deploy.sh` (GHCR pull → migrate → health), JSON logs, Prometheus `GET /api/v1/metrics/`, optional Sentry DSN, `docs/ops/deploy.md`. Branch `feat/step73-deploy-observability`.

- **Step 72** — CI/CD: Compose Django tests + migrate in Actions, web typecheck, GHCR push on `main`, `MIGRATE_ON_START` entrypoint flag, prod compose stub, `docs/ops/ci-cd.md`. Branch `feat/step72-cicd`.

- **Step 71** — Load/concurrency: match `latency_ms` p95 &lt; 800 ms suite, 8-way Redlock booking race, HTTP harness `backend/scripts/load_step71.py`, ops note `docs/ops/load-concurrency.md`. Branch `feat/step71-load-concurrency`.

- **Step 70** — Security hardening: CORS allow-list + CSRF trusted origins, DRF Redis throttles (auth/match/voice), browser security headers, prod HSTS/SSL cookies, `docs/ops/tls-proxy.md`. Branch `feat/step70-security-hardening`.

- **Step 69** — Privacy: `GET /privacy/export/` (JSON/PDF), `POST /privacy/erase/` (password confirm), FAISS rebuild eviction for caregivers, weekly residual purge beat task, Account → Privacy UI. Branch `feat/step69-erasure-export`.

- **Step 68** — Shared Fernet PHI encryption: voice intent transcript/condition, dialogue turns/chips, health metadata/payloads, MatchRun query/condition; medical-records helpers re-export shared module. Branch `feat/step68-field-encryption`.

- **Step 67** — Mobile push: `expo-notifications` + device token register/unregister, care-request events also queue FCM/APNs, `eas.json` (development/preview/production). Branch `feat/step67-mobile-push-eas`.

- **Step 66** — Mobile caregiver Accept/Reject (+ optional reason), patient Cancel; Messages screen with current-thread poll chat. Branch `feat/step66-mobile-inbox-messaging`.
- **Step 65** — Mobile match cards with VEHMF breakdown bars, profile-gated Request caregiver (`createCareRequest` + snapshot), requests list screen. Branch `feat/step65-mobile-match-request`.
- **Step 64** — Mobile Serah: Skia Neural Core, Goal Ring + chips, Zustand FSM, text → `POST /voice/turn/` with consent gate and match preview. Branch `feat/step64-mobile-neural-core`.
- **Step 63** — Expo mobile auth: SecureStore JWT session, AuthProvider, login/register (patient|caregiver), role hub navigation, API token refresh wiring. Branch `feat/step63-mobile-auth`.
- **Step 62** — Expo mobile bootstrap: `apps/mobile` (Expo 52 + expo-router), Metro monorepo config, shared `@care-plus/{core,api-client,ui-tokens}`, health-check shell. Branch `feat/step62-expo-bootstrap`.
- **Step 61** — Content polish: Sri Lanka–appropriate empty states and microcopy; remove literal “placeholder” NIC label, HIPAA/stub jargon; catalog/checkout empties. Branch `feat/step61-copy-polish`.
- **Step 60** — Accessibility: skip links, menu focus traps, ARIA live/alerts, Escape-to-stop Neural Core, language radiogroup keys, reduced-motion CSS, muted contrast bump, Vitest+axe on auth/home/results. Branch `feat/step60-a11y-pass`.
- **Step 59** — UI i18n: `packages/core` en/si/ta catalogs + `t()`; `LocaleProvider` / language switcher (`careplus.uiLocale`); public home, login, platform hub + headers translated. Branch `feat/step59-ui-i18n`.
- **Step 15h** — Unified Neural Core loop: `CHAT_REPLY` FSM state, scrollable `ChatBubbles`, MATCHING→RESULTS transition, mic re-arms after Serah TTS in conversation mode. Branch `feat/step15h-conversation-loop`.
- **Step 15j** — Dialogue AI policy: `DIALOGUE_CHAT_BACKEND` + Gemini chat rate limit; MATCH/REFINE stay VEHMF-only; `GET /voice/policy/`; turn `chat_source` + audit; docs in `DIALOGUE_POLICY.md`. Branch `feat/step15j-dialogue-policy`.
- **Step 23** — CareRequest: `draft|pending|accepted|rejected|cancelled|expired` states; `POST/GET /care-requests/`; patient cancel; match snapshot; hourly expiry Celery task; `/requests` UI. Branch `feat/step23-care-request`.
- **Step 22** — `get_cf_model()` wires ALS into `VEHMFEngine`; `CF_ENABLED=false` redistributes β; match + weights API expose CF metadata; offline NDCG/MAP regression tests. Branch `feat/step22-cf-blend`.
- **Step 21** — `Interaction` model (view/request/accept/complete/rate); logging on match + caregiver detail; `seed_interactions` + `train_cf` (implicit ALS); versioned `ml/artifacts/cf/`; Celery beat nightly `matching.train_cf_model`. Branch `feat/step21-cf-interactions`.
- **Step 15i** — Refine phrases → language/distance/specialty/care_level deltas; VEHMF hard filters + closer geo tilt; match cards show ↑↓ rank deltas + latency; `refined` flag. Branch `feat/step15i-post-match-refine`.
- **Step 15g** — `DialogueSession` stores chips, route history, last N turns, last `MatchRun`; turn response includes `session_id`; `GET /voice/session/` + `POST /voice/session/clear/`; Home **New request** clears server+client memory. Branch `feat/step15g-session-memory`.
- **Step 20e** — Soft presence: VEHMF hides unavailable from top-N; `GET/PATCH /caregivers/me/`; web `/presence` toggle; browse already filters `?available=`. Branch `feat/step20e-availability`.
- **Step 15f natural conversation router** — After matches, “thank you” / ස්තූතියි / நன்றி stay CHAT (no re-match); situations for goodbye, affirm, about_match, refine, action, emergency; situational Serah stubs + Gemini guidance. Branch `feat/dialogue-natural-conversation`.
- **Fix voice turn 401 / empty ASR** — JWT refresh on 401; MediaRecorder flush; clearer empty-mic vs bad-ASR Serah replies; multi-commit branch `fix/voice-turn-401-empty-asr`.
- **Step 20d** — Caregiver detail: `GET /caregivers/<id>/` + audited view; web `/caregivers/:id` (bio, certs, languages, specialties, trust, area, reviews teaser, Request CTA stub); browse + match cards link in. Branch `feat/step20d-caregiver-detail`.
- **Voice lang picker + STT/TTS framework** — Explicit සිංහල|தமிழ்|English locks captions, Whisper ASR, and Serah replies; `apps.voice.tts` (Piper → Gemini TTS → browser); `/voice/turn/` returns `reply_audio_*` + `tts_source`. Branch `feat/voice-lang-picker-tts`.
- **Step 20c** — `/caregivers` browse: search, language/specialty chips, Leaflet dark map, list + empty/error; api-client `caregivers()`. Branch `feat/step20c-browse-ui`.
- **Step 20b** — Expand `GET /caregivers/` with combinable `q/language/specialty/city/care_level/available` + PostGIS `near/radius_km`, pagination, `city`/`is_available` fields. Branch `feat/step20b-caregiver-search`.
- **Step 15b** — `apps.vocab`: `ConditionTerm` + `seed_vocab` (37 Sri Lanka terms with si/ta/en synonyms); `GET /api/v1/vocab/conditions/`; voice stub/Gemini resolve to slugs (`ඩෙංගු`→`dengue`, “sugar problem”→`diabetes`). Branch `feat/step15b-medical-vocab`.
- **Conversational voice** — `POST /voice/turn/` (audio+text); **language picker** locks ASR+TTS; **local faster-whisper** ASR; pluggable TTS (`auto`/`piper`/`gemini_tts`/`browser`); Gemini ASR optional.
- **Auto + mixed language** — Removed manual lang picker; ASR auto-picks si/ta/en; intent returns `languages[]` for Singlish/Tanglish; primary `language` still drives match. Gemini key loaded after `docker compose up --force-recreate backend`. Branch `feat/auto-multilang-voice`.
- **Docs v0.3** — Added **M3c (15f–15j)** conversational dialogue: turn router (CHAT|MATCH|REFINE|ACTION|EMERGENCY), session memory, unified mic loop, post-match refine, Gemini/local policy. Locked: Gemini never ranks caregivers. Branch `docs/conversational-serah-loop`.
- **Step 20** — JWT match WebSocket + push from `POST /match/`; api-client `match()`; HomePage SPEAKING→MATCHING→RESULTS; `MatchResultCards` (breakdown bars, XAI, latency, Request CTA stub). Branch `feat/step20-match-ux`.
- **Step 19** — `VEHMFEngine.predict`: FAISS CBF + stub CF + PostGIS geo decay + trust; AHP fusion; XAI text; persists `MatchRun`/`MatchResult`; consent-gated `POST /api/v1/match/` returns ranked list + breakdown + `latency_ms`. 6 tests green. Branch `feat/step19-vehmf-engine`.
- **Step 18** — AHP solver (`apps.matching.ahp`): principal eigenvector of pairwise survey → `[CBF, CF, Geo, Trust]` weights summing to 1 with CR≈0.019; `config/ahp_weights.json`; emergency vector `[0.80,0.05,0.05,0.10]`; env overrides `AHP_WEIGHTS` / `AHP_EMERGENCY_WEIGHTS`; `build_ahp_weights` command; `GET /api/v1/match/weights/`. Branch `feat/step18-ahp-weights`.
- **Step 17** — Pluggable embedders (`hash` default / optional `e5`); FAISS `IndexFlatIP`; persist vectors on `CaregiverProfile` + `ml/artifacts/`; management commands `build_caregiver_index` + `query_caregiver_index`; consent-gated `POST /api/v1/match/cbf/`. Query “diabetes Sinhala intermediate Colombo” ranks diabetes caregivers first. 6 FAISS tests green. Branch `feat/step17-embeddings-faiss`.
- **Docs v0.2** — Expanded plan to **75 steps** across M0–M17 using Old Care Plus/Lumora as product completeness reference; added `PRODUCT_VISION.md` (Old→New matrix). Branch `docs/full-product-plan`.
- **Fix** — Dengue vocab + CLARIFYING continue loop (PR #14).
- **Step 16** — `apps.matching` profiles + Sri Lanka `seed_profiles`; `GET /caregivers/`.
- **Fix** — Neural Core neuron cloud (no square Bloom fill) (PR #12).
- **Step 15** — Voice → intent UI end-to-end (PR #11).
- **Step 14** — Backend voice/intent Gemini+stub, consent-gated.
- **Step 13** — Web Speech live transcript.
- **Steps 9–12** — Web shell, auth, Neural Core, assistant FSM.
- **Steps 6–8** — JWT/RBAC, consent, audit.
- **Steps 1–5** — Foundations + CI.
