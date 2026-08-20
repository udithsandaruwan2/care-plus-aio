# Care Plus — Engine & Experience Development Plan (v0.4)

> **Status:** Active build plan **v0.4** (AI engine, offline, history trail, self-improving ranking)
> Continues [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) **v0.3** — that plan is complete through **M17 / Step 75**.
> Companions: [ARCHITECTURE.md](ARCHITECTURE.md) · [FRONTEND.md](FRONTEND.md) · [DIALOGUE_POLICY.md](DIALOGUE_POLICY.md) · [THESIS_METHODOLOGY.md](THESIS_METHODOLOGY.md) · [PROGRESS.md](../PROGRESS.md)
> **Scope:** v0.3 built the product. v0.4 makes the **engine** faster to feel, cheaper to run, usable offline, fully auditable, and able to learn from its own outcomes.

---

## How to use this plan

1. Build **one numbered step at a time** on branch `feat/stepN-<slug>` off updated `main`.
2. Each step has **Goal · Tasks · ✅ Acceptance · Depends on**.
3. Do not start a step until its dependencies pass acceptance. Steps with no dependency listed are parallel-safe.
4. Push after development; PR → **merge** when the step is complete.
5. Update [PROGRESS.md](../PROGRESS.md) every step.

Step numbering continues from v0.3 (which ended at Step 75), so branch names never collide.

---

## 0. Why this plan exists

An audit of the voice pipeline, the VEHMF engine, and the web client found the platform is feature-complete but has four structural gaps:

| Gap                       | Evidence in current code                                                                                                     |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Leaky learning loop**   | `INTERACTION_WEIGHTS` defines COMPLETE 8.0 and RATE 1.0×rating; neither is ever written. CF trains almost entirely on VIEW 1.0 |
| **Blocking conversation** | `process_turn()` runs ASR → intent → route → VEHMF → chat → TTS in one synchronous response; nothing streams                  |
| **No AI audit trail**     | Match runs write no `AuditLog` row; `GRANT_CONSENT` / `LOGIN` exist in the enum and are never written; no `request_id` on audit |
| **No offline client**     | Service worker handles push only — no manifest, no fetch handler, no cache; `LOCAL_LLM_URL` was never implemented              |

Everything below follows from those four. Ordering matters: **M18 must land first**, because the model-quality and adaptive-ranking milestones are all downstream of the signals it captures.

---

## 0b. Decisions locked (v0.4)

| #   | Decision                | Locked default                                                                          | Note                                                                        |
| --- | ----------------------- | --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| 13  | Offline intent          | **Small multilingual slot classifier**, not a quantized local LLM                        | Closed vocabulary; ms on CPU; trains on our own `VoiceIntent` rows           |
| 14  | Local LLM               | Optional **fallback for open chat only**, behind `LOCAL_LLM_URL`                          | Never on the match path; 3B on 2 vCPU is too slow to be primary             |
| 15  | Turn transport          | **Stream stages over existing `ws/match/` Channels layer**                                | No SSE, no new infra; HTTP response stays as the non-streaming fallback     |
| 16  | Fusion weights          | **AHP stays the prior and the explainable fallback**; learned weights layer on top        | Thesis defensibility is preserved                                           |
| 17  | Model promotion         | **Gated** — a new artifact only becomes `current` if it beats the incumbent on holdout    | Today `train_cf_als()` promotes unconditionally                             |
| 18  | Offline ranking         | **Hash embedder reimplemented in TS** for on-device cosine ranking                        | Feasible only because the lean default embedder has no weights              |
| 19  | Retention               | Explicit **TTL per data class** for active accounts, not just erasure                     | Erasure + 30-day purge already exist                                        |
| 20  | Provenance              | Every ranking reproducible from the DB alone                                              | Model versions, filters, and intent link must be persisted on `MatchRun`    |

---

## 1. Milestone map (v0.4 — 31 steps)

| Milestone                              | Steps     | Outcome                                                            |
| -------------------------------------- | --------- | ------------------------------------------------------------------ |
| **M18 · Signal & telemetry foundations** | 76–79   | Outcomes logged, stages timed, AI decisions audited and reproducible |
| **M19 · Client efficiency**              | 80–82   | Smaller first load, calmer render loop, network-tolerant boot        |
| **M20 · Conversation feel**              | 83–87   | Streaming turns, interruptible speech, recoverable failures          |
| **M21 · Model lifecycle**                | 88–92   | Registry, auto index rebuild, replay eval, gated promotion, negatives |
| **M22 · Offline & local intelligence**   | 93–98   | Installable PWA, cached reads, queued writes, local slot model       |
| **M23 · Adaptive ranking**               | 99–103  | Cold-start clustering, exploration, learned weights, A/B, fairness   |
| **M24 · History surface & retention**    | 104–106 | User-visible trail, complete export, retention policy                |

**Start at Step 85.** M20 continues with barge-in during Serah playback.

---

## M18 · Signal & telemetry foundations

> **Why first:** every later milestone measures itself against data that is not being captured today.

### Step 76 — Outcome interaction logging ✅ **DONE**

**Branch:** `feat/step76-outcome-interactions`
**Goal:** collaborative filtering trains on what actually happened, not on what was displayed.
**Done:**

- `InteractionKind.REJECT` (weight −1.0) logged from `reject_care_request()`.
- `COMPLETE` (weight 8.0) logged from `end_relationship()` when the prior status was `active`.
- `RATE` (weight 1.0 × stars) logged when a patient submits a review.
- `backfill_interactions` derives missing COMPLETE / RATE / REJECT rows from existing records using an `outcome_key` fingerprint; running twice is a no-op. `seed_demo` calls it after the showcase graph.
- Implicit ALS skips non-positive weights so REJECT does not break training (Step 92 consumes the negatives).

**✅ Acceptance:** all six interaction kinds appear after a hire funnel + backfill; running the backfill twice produces no duplicates; `train_cf_als` still trains when COMPLETE rows are present.

---

### Step 77 — Per-stage voice turn telemetry ✅ **DONE**

**Branch:** `feat/step77-turn-telemetry`
**Goal:** know where the seconds actually go. Today only `match.latency_ms` is measured, so the documented sub-800 ms figure excludes Whisper, Gemini, and TTS.
**Done:**

- `process_turn()` returns `timings` (`asr_ms`, `intent_ms`, `route_ms`, `match_ms`, `chat_ms`, `tts_ms`, `total_ms`, `request_id`).
- Structured JSON logs `voice.turn.timings` include the same fields plus `request_id` from the request-id middleware.
- `VoiceTurnTiming` persists stage times (no transcript); admin analytics exposes `turn_latency` p50/p95/p99 next to match-engine latency.
- README + ARCHITECTURE §11 distinguish VEHMF engine time (< 800 ms) from full voice-turn wall time.

**✅ Acceptance:** every `/voice/turn/` response carries all stage timings; their sum is within 50 ms of measured wall time; a turn is joinable by `request_id` on the log line, audit metadata, and `VoiceTurnTiming` row.

---

### Step 78 — AI decision audit rows ✅ **DONE**

**Branch:** `feat/step78-ai-audit`
**Goal:** close the audit blind spot on the AI path.
**Done:**

- `AuditAction.RUN_MATCH` is written once per `create_match_run()` (HTTP `/match/`, voice dialogue, emergency rematch, shift conflict fallback, demo seed).
- `GRANT_CONSENT` / `REVOKE_CONSENT` are written from `ConsentLogSerializer.create()`.
- `LOGIN` is written when JWT credentials succeed (`CarePlusTokenObtainPairSerializer`).
- `AuditLog.request_id` stores the HTTP correlation id at enqueue time so Celery workers still persist it. List/CSV/admin expose the column.

**✅ Acceptance:** one voice match writes exactly one match audit row; a consent toggle writes a grant then a revoke; every audit row originating from an HTTP request carries a `request_id` that joins to the JSON logs; the append-only Postgres trigger still rejects updates and deletes.

---

### Step 79 — MatchRun provenance & replay ✅ **DONE**

**Branch:** `feat/step79-matchrun-provenance`
**Goal:** answer "why was this caregiver recommended to this patient on this date" from the database alone.
**Done:**

- `MatchRun` stores `cf_version`, `embedding_backend`, `index_version`, `weights_source`, `filters` (including refine flags), `voice_intent`, and `request_id`.
- FAISS `caregivers.ids.json` is stamped with a membership hash so `index_version` changes when the pool changes.
- `python manage.py replay_match <run_id>` re-runs VEHMF and reports identical ranking vs artifact/ranking drift.
- Privacy JSON export includes per-caregiver CBF/CF/geo/trust scores and fusion weights.

**✅ Acceptance:** `replay_match` reproduces an identical ranking when the referenced artifacts are unchanged, and reports a clear mismatch when they are not; the export contains per-caregiver factor scores.

---

## M19 · Client efficiency

### Step 80 — Web first-load budget ✅ **DONE**

**Branch:** `feat/step80-bundle-split`
**Goal:** stop shipping the admin charts and the map to someone who only opens Serah.
**Done:**

- Every page in `App.tsx` is `React.lazy` behind a shared suspense fallback.
- `manualChunks` isolate `recharts`, `leaflet`, and `three`; they are not modulepreloaded on first paint.
- Removed unused `@react-three/drei`, `@react-three/postprocessing`, and `postprocessing`.
- Fonts are self-hosted via `@fontsource` (Inter + Noto Sans Sinhala/Tamil); Google Fonts CDN is gone.
- CI job `web-bundle` runs `vite build` + `check-entry-budget` (entry JS under 450 KB uncompressed).

**✅ Acceptance:** entry chunk under 450 KB uncompressed (from ~1.1 MB); analytics and browse resolve as separate chunks on navigation; no third-party font request in the network panel; CI fails if the entry chunk regresses past the budget.

---

### Step 81 — Render and input loop budget ✅ **DONE**

**Branch:** `feat/step81-render-budget`
**Goal:** the neural core should idle cheaply on a mid-range laptop and a phone.
**Done:**

- `NeuralMesh` ticks at ~30 fps except speaking/emergency (60 fps). The 104-neuron instance buffer is skipped when amplitude and state are unchanged.
- Removed `invalidate()` from the always-on frame loop.
- Canvas uses `frameloop="demand"` when the tab is hidden, reduced-motion is on, or IntersectionObserver reports the canvas off-screen (zero frames).
- Mic level is read from a ref in the render loop; React `amplitude` publishes at most ~15 Hz.

**✅ Acceptance:** idle work is at most half of the previous 60 fps × 104-matrix × 60 Hz React path (see PR); off-screen canvases do not animate; reduced-motion still requests one static frame; speech/emergency still drive the orb.

---

### Step 82 — Network-tolerant client ✅ **DONE**

**Branch:** `feat/step82-network-tolerance`
**Goal:** a flaky connection should degrade the app, not log the user out.
**Done:**

- `refreshMe()` clears the session only on 401/403; transport failures keep the cached user and set `sessionStale`.
- API client: 30s timeout (`TimeoutError`), bounded GET retries with backoff, `NetworkError` on failed fetch; token refresh no longer clears tokens on network failure.
- AppShell banner reflects `navigator.onLine` plus request outcomes (`online` / `offline` / `degraded`).

**✅ Acceptance:** with the network disabled, a reload keeps the user signed in and shows an offline indicator instead of the login screen; a stalled request aborts at the configured timeout with a typed error.

---

## M20 · Conversation feel

### Step 83 — Streaming voice turn ✅ **DONE**

**Branch:** `feat/step83-streaming-turn`
**Goal:** the biggest perceived-latency win. Show the user each stage as it completes instead of after all six.
**Done:**

- `process_turn()` emits staged events over `ws/match/<user_id>/`: `transcript` → `intent` → `route` → `reply_text` → `match` → `reply_audio` → `done`.
- HTTP `/voice/turn/` response shape unchanged as the non-streaming fallback.
- Client applies `turn.*` frames progressively and skips duplicate UI/TTS work when the HTTP response lands for the same `request_id`.

**✅ Acceptance:** the transcript appears in the UI before matching starts; reply text appears before audio is synthesized; disconnecting the socket falls back to the existing single-response behaviour with no user-visible error.
**Depends on:** Step 77 (timings prove the improvement).

---

### Step 84 — Unblock the reply from speech synthesis ✅ **DONE**

**Branch:** `feat/step84-tts-decouple`
**Goal:** stop making the user wait for audio they have not started listening to.
**Done:**

- `first_text_ms` recorded before TTS; `turn.reply_text` already streams ahead of audio (Step 83).
- Uncached server TTS is deferred off the HTTP response (`audio_pending`); audio arrives via `turn.reply_audio` or `POST /voice/tts/`.
- Redis phrase cache keyed on hash(text + language + voice); hit/miss rate logged as `tts.phrase_cache`.

**✅ Acceptance:** `tts_ms` no longer contributes to time-to-first-text; repeated canned phrases serve from cache with a hit rate above 60% in a scripted five-turn session; audio still plays for Sinhala and Tamil.
**Depends on:** Step 83.

---

### Step 85 — Barge-in

**Branch:** `feat/step85-barge-in`
**Goal:** let the user interrupt Serah instead of waiting for her to finish.
**Tasks:**

- Keep the mic analyser active during playback and cancel audio when speech energy crosses a threshold for a sustained window.
- Remove the serialization where `await speakSerah()` blocks the next listen cycle.
- Guard against the assistant hearing its own output (echo threshold or output-device gating).
- Files: `apps/web/src/assistant/useTts.ts`, `apps/web/src/assistant/useVoiceTurn.ts`, `apps/web/src/assistant/SerahEngine.tsx`.

**✅ Acceptance:** speaking over Serah stops playback within ~300 ms and starts a new turn; playing a long reply into an empty room does not self-trigger.
**Depends on:** Step 84.

---

### Step 86 — Recoverable turns

**Branch:** `feat/step86-turn-recovery`
**Goal:** a dropped connection mid-turn should not throw away what the user just said.
**Tasks:**

- Preserve the transcript on failure and offer an inline retry that resubmits the same turn.
- Distinguish network failure, timeout, throttle (429), and consent (451) in the UI copy.
- Queue the turn for replay when the connection returns.
- Files: `apps/web/src/assistant/useVoiceTurn.ts`, `apps/web/src/assistant/ChatBubbles.tsx`.

**✅ Acceptance:** killing the network mid-turn leaves the transcript on screen with a working retry; restoring the network replays the turn once, not twice.
**Depends on:** Step 82.

---

### Step 87 — Reply rendering and card density

**Branch:** `feat/step87-reply-render`
**Goal:** reduce the reading cost of both the reply and the results.
**Tasks:**

- Render reply text progressively as stream events arrive.
- Collapse the four-factor VEHMF breakdown behind a disclosure on match cards; lead with name, score, and the one-line reason.
- Generate a comparative line from the factor breakdown already stored on `MatchResult`, so the user can see why #1 beat #2.
- Add an accessible label and a polite live region announcing assistant state, and give the decorative canvas a text alternative.
- Files: `apps/web/src/assistant/ChatBubbles.tsx`, `apps/web/src/assistant/MatchResultCards.tsx`, `apps/web/src/assistant/NeuralOrb.tsx`.

**✅ Acceptance:** results fit the viewport with the breakdown collapsed; expanding one card does not shift the others; axe reports no new violations and state changes are announced.
**Depends on:** Step 83.

---

## M21 · Model lifecycle

### Step 88 — Model registry

**Branch:** `feat/step88-model-registry`
**Goal:** know from the database which model produced which result.
**Tasks:**

- Add a `ModelVersion` model: `kind` (cf / faiss / slot-classifier), `version`, `trained_at`, `rows_trained_on`, `metrics` (JSON), `is_active`, `artifact_path`.
- Write a row on every training run; make `MatchRun.cf_version` and `index_version` foreign keys or resolvable strings.
- Expose read-only rows in the admin console.
- Files: `backend/apps/matching/models.py`, `backend/apps/matching/cf_train.py`, `backend/apps/matching/faiss_index.py`.

**✅ Acceptance:** the admin console lists every trained artifact with its metrics; exactly one row per kind is active; a `MatchRun` resolves to the model rows that produced it.
**Depends on:** Step 79.

---

### Step 89 — Automatic index rebuild

**Branch:** `feat/step89-index-refresh`
**Goal:** a caregiver who edits their specialties should rank differently without a human running a command.
**Tasks:**

- Enqueue a Celery re-embed task on caregiver profile save that updates just that caregiver's vector.
- Add a periodic consistency rebuild for drift, and a dirty-flag path for bulk changes.
- Handle deactivation and erasure eviction in the same path.
- Files: `backend/apps/matching/views.py`, `backend/apps/matching/faiss_index.py`, `backend/apps/matching/tasks.py`.

**✅ Acceptance:** editing a caregiver's specialties changes their rank for a relevant query within one task cycle, with no manual command; the scheduled rebuild is a no-op when nothing changed.
**Depends on:** Step 88.

---

### Step 90 — Replay evaluation harness

**Branch:** `feat/step90-eval-harness`
**Goal:** promote the single NDCG unit test into something that can judge a candidate model.
**Tasks:**

- Add `eval_ranking` management command that replays historical `MatchRun` rows against a candidate model and reports NDCG@5, MAP, recall@10 against real accepts, plus catalogue coverage and exposure Gini.
- Define a held-out recent time window rather than a random split, so evaluation respects causality.
- Add `precision_at_k` alongside the existing `ndcg_at_k` and `average_precision`.
- Files: `backend/apps/matching/cf_eval.py`, `backend/apps/matching/management/commands/eval_ranking.py`.

**✅ Acceptance:** the command prints a metric table for the active model on seeded history and completes in under two minutes on the demo dataset; metrics are reproducible across runs.
**Depends on:** Steps 76, 79.

---

### Step 91 — Gated model promotion

**Branch:** `feat/step91-gated-promotion`
**Goal:** a worse model must not silently become production. `train_cf_als()` currently flips the pointer unconditionally.
**Tasks:**

- After training, evaluate the candidate against the incumbent on the held-out window.
- Only update `current.json` and mark the `ModelVersion` active if the candidate wins on the primary metric by a configured margin.
- Record both models' metrics on the `ModelVersion` rows and log the decision.
- Add a `promote_model --force` escape hatch for operators.
- Files: `backend/apps/matching/cf_train.py`, `backend/apps/matching/tasks.py`.

**✅ Acceptance:** deliberately training on shuffled interactions produces a candidate that is rejected and leaves the incumbent active; a genuine improvement is promoted and logged.
**Depends on:** Steps 88, 90.

---

### Step 92 — Negative feedback in training

**Branch:** `feat/step92-negative-signals`
**Goal:** teach the model what a bad match looks like. Implicit ALS on positives only cannot distinguish a caregiver who is constantly rejected from one who is never shown.
**Tasks:**

- Feed the `REJECT` rows from Step 76 into training as explicit negatives.
- Move to a ranking objective that uses them — BPR, or ALS with per-observation confidence weighting.
- Treat shown-and-not-acted-on as a weak negative, distinct from an explicit reject.
- Compare against the incumbent using the Step 90 harness before adopting.
- Files: `backend/apps/matching/cf_train.py`, `backend/apps/matching/cf_model.py`.

**✅ Acceptance:** the new objective beats the current ALS on NDCG@5 and recall@10 on the held-out window, with numbers recorded in the PR; `CF_ENABLED=false` still cleanly redistributes β.
**Depends on:** Steps 76, 90, 91.

---

## M22 · Offline & local intelligence

### Step 93 — Installable PWA shell

**Branch:** `feat/step93-pwa-shell`
**Goal:** the app should open with no network. The service worker currently handles push only.
**Tasks:**

- Add `vite-plugin-pwa` with Workbox, preserving the existing push handler rather than replacing it.
- Add a web app manifest, icons, and the manifest link in `index.html`.
- Precache the app shell and self-hosted fonts; set an explicit runtime cache strategy per route class.
- Add an explicit offline screen instead of a silent failure.
- Files: `apps/web/vite.config.ts`, `apps/web/public/sw.js`, `apps/web/index.html`.

**✅ Acceptance:** the app installs and opens offline to a usable shell; web push still works after the service worker upgrade; a hard reload offline does not white-screen.
**Depends on:** Steps 80, 82.

---

### Step 94 — Cached reads

**Branch:** `feat/step94-offline-reads`
**Goal:** stop refetching everything on every mount, and make recent data readable offline. There is no query cache today — each page uses its own `useState` + `useEffect`.
**Tasks:**

- Introduce a query layer with an IndexedDB persister.
- Migrate the profile, match, browse, and message hooks onto it.
- Cache last match results, viewed caregiver profiles, and message threads with per-entity staleness rules.
- Mark stale-while-offline data visibly rather than presenting it as live.
- Files: `apps/web/src/auth/*`, `apps/web/src/pages/*`, `apps/web/src/lib/`.

**✅ Acceptance:** with the network off, the last match results and an opened caregiver profile still render, clearly badged as cached; navigating between pages online no longer refetches unchanged data.
**Depends on:** Steps 82, 93.

---

### Step 95 — Queued writes

**Branch:** `feat/step95-offline-outbox`
**Goal:** a care request or message composed offline must not be lost.
**Tasks:**

- Add an IndexedDB outbox replayed via Background Sync, with visible pending state per item.
- Add server-side idempotency keys on care-request creation, messaging, and payment confirmation so a replay cannot double-book or double-charge.
- Handle permanent failures (validation, 451) by surfacing them rather than retrying forever.
- Files: `packages/api-client/src/client.ts`, `backend/apps/matching/views.py`, `backend/apps/messaging/views.py`.

**✅ Acceptance:** a care request created offline is queued, shown as pending, and submitted exactly once on reconnect; replaying the same idempotency key returns the original result rather than creating a duplicate.
**Depends on:** Step 94.

---

### Step 96 — Local slot classifier

**Branch:** `feat/step96-slot-classifier`
**Goal:** offline intent understanding that improves with use — the bridge between offline support and self-improvement.
**Tasks:**

- Build a training pipeline over logged `VoiceIntent` rows (raw text → condition, language, care level, urgency), using the canonical vocab as the label space.
- Train a small multilingual classifier (fastText or distilled MiniLM) sized in tens of megabytes; hold out a recent window for evaluation.
- Register the artifact as a `ModelVersion` and retrain on the same gated-promotion path as CF.
- Note the label-bias risk: training on Gemini-extracted labels teaches the classifier to imitate Gemini. Reserve a small hand-labelled set for honest evaluation.
- Files: `ml/train_slots.py`, `backend/apps/voice/slots.py`, `backend/apps/matching/models.py`.

**✅ Acceptance:** the classifier reaches agreed accuracy on the hand-labelled si/ta/en holdout, runs under 50 ms per utterance on the lean CPU profile, and beats the existing rule-based stub extractor on the same set.
**Depends on:** Steps 88, 91.

---

### Step 97 — Local backend wiring

**Branch:** `feat/step97-local-backend`
**Goal:** implement the `LOCAL_LLM_URL` slot that has been an empty setting since v0.3.
**Tasks:**

- Make `VOICE_INTENT_BACKEND=local` use the Step 96 classifier instead of returning the stub.
- Add an optional OpenAI-compatible local endpoint for open-ended chat replies only, never for the match path.
- Define the fallback chain explicitly: local classifier → Gemini → stub, with the reason recorded per turn.
- Document the fully offline deployment profile.
- Files: `backend/apps/voice/backends.py`, `backend/apps/voice/extraction.py`, `docs/DIALOGUE_POLICY.md`.

**✅ Acceptance:** with `GEMINI_API_KEY` unset and no internet, a Sinhala utterance still produces correct chips and a real VEHMF match; the turn payload records which backend served it.
**Depends on:** Step 96.

---

### Step 98 — On-device ranking fallback

**Branch:** `feat/step98-edge-ranking`
**Goal:** a rough ranked list with no server, feasible because the lean default embedder is deterministic feature hashing with no weights.
**Tasks:**

- Reimplement `HashEmbedder` in TypeScript in `packages/core` with a parity test against the Python implementation.
- Cache a bounded nearby caregiver subset with their vectors in IndexedDB.
- Compute cosine ranking client-side when offline; label the results clearly as provisional.
- Reconcile against the authoritative VEHMF result on reconnect and record the divergence.
- Files: `packages/core/src/embedding.ts`, `apps/web/src/assistant/offlineMatch.ts`, `backend/apps/matching/embeddings.py`.

**✅ Acceptance:** TS and Python embedders produce identical vectors for a shared fixture set; an offline query returns a provisional ranked list; reconnecting replaces it with the server result.
**Depends on:** Steps 94, 97.

---

## M23 · Adaptive ranking

### Step 99 — Cold-start clustering

**Branch:** `feat/step99-cold-start-clusters`
**Goal:** a caregiver absent from the trained factors currently scores a flat 0.0 and is structurally disadvantaged.
**Tasks:**

- Cluster caregiver embeddings and seed a new caregiver with their cluster's average CF vector until they accumulate real interactions.
- Cluster patient intent embeddings to surface the actual demand taxonomy; feed it back into the canonical vocab and condition resolution.
- Add an admin view of both cluster sets for inspection.
- Files: `backend/apps/matching/cf_model.py`, `backend/apps/matching/clustering.py`, `backend/apps/vocab/`.

**✅ Acceptance:** a newly onboarded caregiver receives a non-zero, plausible CF score before their first interaction; overall NDCG on the holdout does not regress; the intent clusters surface at least one condition grouping not already in the vocab.
**Depends on:** Steps 90, 92.

---

### Step 100 — Exploration slot

**Branch:** `feat/step100-exploration`
**Goal:** greedy ranking only ever collects feedback about caregivers it already ranks highly, which starves new joiners and biases every model trained downstream.
**Tasks:**

- Reserve one top-K slot for an exploration policy (epsilon-greedy first, Thompson sampling as a follow-up).
- Record `was_exploratory` on `MatchResult` so counterfactual analysis is possible later.
- Make the exploration rate configurable and disabled by default in emergency runs.
- Files: `backend/apps/matching/engine.py`, `backend/apps/matching/models.py`.

**✅ Acceptance:** over a simulated run, caregiver exposure Gini falls measurably against `main`; emergency matches never explore; exploratory results are flagged in the stored run.
**Depends on:** Steps 79, 90.

---

### Step 101 — Learned fusion weights

**Branch:** `feat/step101-learned-fusion`
**Goal:** adapt the four weights to context while keeping AHP as the explainable prior and cold-start default.
**Tasks:**

- Fit weights against accept outcomes using stored `MatchResult` features, segmented by emergency versus routine and urban versus rural.
- Fall back to the AHP vector whenever a segment lacks sufficient data.
- Keep the consistency-ratio check and `GET /match/weights/` reporting which source produced the active weights.
- Files: `backend/apps/matching/ahp.py`, `backend/apps/matching/engine.py`, `backend/apps/matching/weights_train.py`.

**✅ Acceptance:** learned weights beat static AHP on holdout NDCG@5 for at least one segment; sparse segments provably fall back to AHP; the XAI explanation still names a dominant factor.
**Depends on:** Steps 90, 91, 100.

---

### Step 102 — Online A/B on weight variants

**Branch:** `feat/step102-weight-ab`
**Goal:** validate ranking changes on live outcomes instead of holdout metrics alone.
**Tasks:**

- Deterministic user-level assignment to weight variants; record `variant` on `MatchRun`.
- Add an admin comparison view of accept rate, completion rate, and time-to-accept per variant.
- Document the stopping rule so results are not read early.
- Files: `backend/apps/matching/experiments.py`, `backend/apps/matching/models.py`, admin analytics.

**✅ Acceptance:** assignment is stable per user across sessions; the comparison view reports per-variant outcome rates with sample sizes; a variant can be retired without redeploying.
**Depends on:** Steps 76, 101.

---

### Step 103 — Ranking guardrails

**Branch:** `feat/step103-ranking-guardrails`
**Goal:** the engine currently has no fairness, diversity, or approval guardrails, and does not even filter on `is_approved`.
**Tasks:**

- Add the missing `is_approved` filter to the candidate pool.
- Add diversity re-ranking (MMR or similar) so the top-K is not five near-identical profiles.
- Add per-caregiver exposure caps over a rolling window.
- Add a fairness report comparing exposure distribution across language and region.
- Files: `backend/apps/matching/engine.py`, `backend/apps/matching/fairness.py`.

**✅ Acceptance:** unapproved caregivers never appear in results; top-5 language and specialty diversity improves against `main` without an NDCG regression beyond an agreed tolerance; the fairness report runs as a management command.
**Depends on:** Step 100.

---

## M24 · History surface & retention

### Step 104 — User-facing history trail

**Branch:** `feat/step104-history-timeline`
**Goal:** all the provenance data from M18 exists and none of it is visible to the person it describes.
**Tasks:**

- Add a history endpoint returning the user's past turns and match runs with what Serah understood, who was recommended, and what happened next.
- Build a timeline page grouped by session, with the stored XAI explanation per result.
- Let the user delete an individual entry, wired to the existing erasure primitives.
- Files: `backend/apps/voice/views.py`, `backend/apps/matching/views.py`, `apps/web/src/pages/HistoryPage.tsx`.

**✅ Acceptance:** a patient can see every past search with its results and reasons; deleting an entry removes it from the API and from future exports while the audit row is retained.
**Depends on:** Steps 78, 79.

---

### Step 105 — Complete data export

**Branch:** `feat/step105-export-completeness`
**Goal:** the export currently includes match run summaries without results or weights, which is incomplete for a data-subject request.
**Tasks:**

- Include `MatchResult` rows, weights, model versions, consent history, and audit rows in the JSON and PDF exports.
- Paginate or stream so large accounts do not time out.
- Add a test asserting every user-owned model is represented in the export.
- Files: `backend/apps/accounts/privacy.py`.

**✅ Acceptance:** the export for a seeded active patient contains every user-linked table; the completeness test fails if a new user-owned model is added without updating the export.
**Depends on:** Steps 79, 104.

---

### Step 106 — Retention policy

**Branch:** `feat/step106-retention`
**Goal:** active accounts accumulate voice intents, dialogue turns, and health metrics forever. Only erasure and the 30-day residual purge exist.
**Tasks:**

- Define a TTL per data class in settings and enforce it with a scheduled anonymization task.
- Wipe `turns` and `route_history` when a session is cleared — today the session is only marked inactive and the encrypted turn text remains.
- Downsample old health metrics rather than deleting them outright, preserving trend value.
- Document the policy in the privacy notice.
- Files: `backend/apps/voice/session.py`, `backend/apps/accounts/tasks.py`, `backend/careplus/settings/base.py`, privacy notice page.

**✅ Acceptance:** the retention task removes or anonymizes data past its TTL and is idempotent; clearing a session leaves no recoverable turn text; the privacy notice states each retention period.
**Depends on:** Step 105.

---

## Parallel tracks

| Track                     | Steps           | When                                                              |
| ------------------------- | --------------- | ----------------------------------------------------------------- |
| A · Signals & audit       | 76→79           | **First.** Blocks M21 and M23                                     |
| B · Client performance    | 80→82           | Anytime; independent of backend work                              |
| C · Conversation feel     | 83→87           | After 77; 83 blocks 84–85                                         |
| D · Model lifecycle       | 88→92           | After 76 and 79                                                   |
| E · Offline               | 93→98           | After 80, 82; 96 needs 88 and 91                                  |
| F · Adaptive ranking      | 99→103          | After 90 and 92 — do not start before the signal loop is closed   |
| G · History & retention   | 104→106         | After 78, 79                                                      |

Tracks **A** and **B** can run concurrently from day one. **F** is deliberately last: fitting adaptive models before the outcome signals exist mainly teaches the system to agree with itself.

---

## Working agreement

1. Branch `feat/stepN-<slug>` off updated `main`.
2. State goal + files touched.
3. Many focused commits per branch is fine; one step per branch.
4. Prove acceptance in the PR body, with numbers where the step names a metric.
5. **Push**; PR → **merge**.
6. Update `PROGRESS.md`.
7. Next step = new branch.

Author identity and the terminal commit recipe: `.cursor/rules/git-workflow.mdc`.

---

## Next up

**Step 85 — Barge-in** on `feat/step85-barge-in`. Let the user interrupt Serah mid-reply.
