# Care Plus — Full Product Development Plan

> **Status:** Active build plan **v0.3** (full-platform + conversational loop)  
> Companions: [ARCHITECTURE.md](ARCHITECTURE.md) · [FRONTEND.md](FRONTEND.md) · [PRODUCT_VISION.md](PRODUCT_VISION.md) · [PROGRESS.md](../PROGRESS.md)  
> **Reference product:** `Old Care Plus/care-plus-main` (Lumora / Care Plus HND platform) — product completeness target, **not** the tech stack to copy.

---

## How to use this plan

1. Build **one numbered step at a time** on branch `feat/stepN-<slug>`.
2. Each step has **Goal · Tasks · Acceptance · Depends on**.
3. Do not start a step until the previous step’s acceptance passes (unless marked parallel-safe).
4. Push after development; PR → merge when the step is complete.
5. Update [PROGRESS.md](../PROGRESS.md) every step.

---

## 0. Decisions locked (lean profile)

| # | Decision | Locked default | Note |
|---|----------|----------------|------|
| 1 | ASR | Web Speech **captions** + server ASR (`ASR_BACKEND=auto` → Gemini audio; `faster_whisper` slot empty) | Browser STT alone is English-biased for si/ta |
| 2 | CF | `implicit` ALS → LightFM upgrade path | Pluggable `CFModel` |
| 3 | Time-series | TimescaleDB | One DB |
| 4 | Embeddings | `intfloat/multilingual-e5-base` (768-d) | FAISS CBF |
| 5 | Hosting | Single VM + Docker Compose, `ap-south` | PDPA proximity |
| 6 | Brand | **Care Plus** product name; **Aurora Neural** design system | Drop dual “Lumora” brand in UI |
| 7 | Matching | **VEHMF** (CBF+CF+Geo+Trust+AHP+XAI) replaces old RF+ad-hoc Gemini rank | Research core |
| 8 | Medical labels | Versioned **canonical vocab** + stub synonyms + Gemini normalize-to-vocab | See M3b / Step 15b |
| 9 | Payments | Real LKR rails later; MVP = verified mock → PayHere/Stripe | Never fake “success” without a PaymentIntent |
| 10 | Comms | In-app messaging + email notifications (not SMTP-as-hire-workflow) | Old `Email` model becomes `CareRequest` + `Message` |
| 11 | Conversation | **One Neural Core mic** = multi-turn dialogue; **router** picks CHAT vs MATCH vs REFINE vs ACTION | Gemini/local for talk; **VEHMF only** for caregiver ranking (never Gemini re-rank) |
| 12 | Intent NLP | `VOICE_INTENT_BACKEND=stub\|gemini\|local` (`LOCAL_LLM_URL` empty until you add a model) | Pluggable local slot |

---

## 1. Product north star (from Old Care Plus)

The finished Care Plus platform must deliver **everything the old app aimed for**, rebuilt with the new architecture:

| Old capability | New delivery |
|----------------|--------------|
| Patient ↔ caregiver Sri Lanka marketplace | Profiles + browse/search + map + VEHMF match |
| ML + Gemini (“Serah”) recommendations | VEHMF + XAI for ranking; Serah = conversational persona (chat + clarify + explain matches) |
| Voice assistant (browser STT/TTS) | **Multi-turn** Neural Core: talk ↔ Serah reply ↔ talk again; router → chat **or** VEHMF match |
| Hire request → accept/reject → pay → active link | First-class `CareRequest` + `CareRelationship` + payments |
| Medical records + health profile | Encrypted records + Timescale vitals (upgrade) |
| Admin analytics + KnownCondition catalog | Admin console + medical vocab admin |
| OTP auth, role dashboards | JWT + optional email OTP; role home shells |
| Care packages (LKR), hospital/food add-ons | Catalog models + checkout (real persistence) |
| Reviews | Moderated reviews with real ratings |
| Static marketing site | React marketing + app (Aurora Neural) |
| *(missing in old)* Mobile | Expo RN patient + caregiver apps |
| *(missing in old)* Realtime health / emergency re-match | Timescale + anomaly + dynamic VEHMF weights |
| *(missing in old)* Scheduling / Redlock | Shift calendar + conflict fallback |

**Do not copy from old:** mock card payment, Windows tray launcher, unused SpeechRecognition deps, RandomForest on postal-code “distance”, hire-via-Email overload, lorem marketing copy, `DEBUG=True` / secrets in repo.

Full mapping: [PRODUCT_VISION.md](PRODUCT_VISION.md).

---

## 2. Milestone map (v0.3 — ~80 steps)

| Milestone | Steps | Outcome |
|-----------|-------|---------|
| **M0 · Foundations** | 1–5 ✅ | Monorepo + Django + DB + Docker + CI |
| **M1 · Auth & Consent** | 6–8 ✅ | JWT, RBAC, consent, audit |
| **M2 · Web shell + Neural Core** | 9–12 ✅ | Aurora Neural + brain + FSM |
| **M3 · Voice → Intent** | 13–15 ✅ | Mic → Gemini/stub → chips + Goal Ring |
| **M3b · Medical vocab & Serah chat** | 15b–15e | Canonical conditions, normalize, grounded Serah API/UI |
| **M3c · Conversational dialogue loop** | 15f–15j | Multi-turn talk ↔ reply; router CHAT vs MATCH vs REFINE |
| **M4 · VEHMF v1 + Match UX** | 16–20 ✅ | Ranked, explained matches (voice → results) |
| **M4b · Marketplace browse** | 20b–20e | Search/filter/map/caregiver detail (old `/caregivers`) |
| **M5 · Personalization (CF)** | 21–22 | ALS blended into fusion |
| **M5b · Profiles & onboarding** | 22b–22f | Rich patient/caregiver profiles (old Profile fields) |
| **M6 · Hire lifecycle** | 23–28 | Request → accept/reject → relationship (old hire flow) |
| **M7 · Catalog, checkout & payments** | 29–33 | Care packages, LKR checkout, payment intents |
| **M8 · Medical records** | 34–37 | Docs, attachments, caregiver access, audit |
| **M9 · Messaging & notifications** | 38–41 | Threads, email/push notifications |
| **M10 · Reviews & trust** | 42–44 | Ratings feed `trust_score` |
| **M11 · Health monitoring** | 45–49 | Timescale, anomalies, emergency re-match, alerts |
| **M12 · Scheduling** | 50–53 | Calendar, Redlock, conflict fallback |
| **M13 · Admin console** | 54–58 | Users, vocab, analytics, appointments/leads |
| **M14 · i18n & accessibility** | 59–61 | si/ta/en UI, a11y, reduced-motion |
| **M15 · Mobile (Expo)** | 62–67 | Patient + caregiver parity |
| **M16 · Compliance & hardening** | 68–71 | Encryption, erasure, TLS, load tests |
| **M17 · Ship** | 72–75 | CI/CD, deploy, stores, launch checklist |

**Current position:** Steps **1–20 done** (voice → VEHMF cards). **Next:** 20b browse, or **15b→15j** for vocab + conversational loop, or 21 CF.  
Prefer closing marketplace/hire when shipping product; run **M3c (15f–15j)** before polish so the mic feels like a real assistant, not a one-shot form.

---

## M0 · Foundations ✅

### Step 1 — Repo & monorepo skeleton ✅
### Step 2 — Docker Compose (Timescale+PostGIS+Redis) ✅
### Step 3 — Django+DRF skeleton + health ✅
### Step 4 — Channels + Celery ✅
### Step 5 — Quality gates (Ruff/Black/Prettier/CI) ✅  
*(Browsable API instead of Swagger — intentional)*

---

## M1 · Auth & Consent ✅

### Step 6 — Custom User + JWT + RBAC ✅
### Step 7 — Consent engine (451 gate) ✅
### Step 8 — Immutable audit trail ✅

---

## M2 · Web shell + Neural Core ✅

### Step 9 — Shared packages + Vite web ✅
### Step 10 — Auth screens ✅
### Step 11 — Neural Core (neuron cloud) ✅
### Step 12 — Assistant FSM + Goal Ring shell ✅

---

## M3 · Voice → Intent ✅

### Step 13 — Web Speech mic + live transcript ✅
### Step 14 — Backend voice/intent (Gemini + stub) ✅
### Step 15 — Chips + Goal Ring end-to-end ✅  
*(Clarify loop + dengue vocab fix shipped)*

---

## M3b · Medical vocabulary & Serah (from old KnownCondition + Serah)

### Step 15b — Canonical medical vocabulary service ✅ **DONE**

**Done:** `apps.vocab.ConditionTerm` (slug, canonical_en, si/ta/en synonyms, active, version); `seed_vocab` (≥37 Sri Lanka terms); `GET /api/v1/vocab/conditions/`; stub/Gemini resolve via vocab (`ඩෙංගු` → `dengue`); admin CRUD.
**✅ Acceptance:** `GET /api/v1/vocab/conditions/` returns ≥30 active terms; stub maps ඩෙංගු → `dengue`; unknown phrase → empty condition + CLARIFYING.

### Step 15c — Extractor wired to vocab (normalize)

**Goal:** Gemini/stub always emit canonical slugs.  
**Tasks:** post-process extractor output through vocab resolver; fuzzy match English synonyms; reject free-text labels outside vocab (or map via Gemini constrained enum).  
**✅ Acceptance:** free text “sugar problem” → `diabetes`; gibberish → `""` + clarify.

### Step 15d — Serah grounded chat API (advice mode)

**Goal:** recreate old `/dashboard/ai` with safety (tool used by the dialogue router).  
**Tasks:** `POST /api/v1/serah/chat` — Gemini (or local stub when no key) with patient profile + recent intents + disclaimer; no diagnosis claims; consent-gated; audit.  
**✅ Acceptance:** authenticated patient gets contextual reply; unauthenticated/no consent → 401/451; response includes disclaimer footer.

### Step 15e — Serah chat UI + TTS

**Goal:** visible chat transcript + optional readback (feeds the unified mic loop in M3c).  
**Tasks:** chat transcript UI; optional `speechSynthesis` readback; link “Ask Serah about this match”.  
**✅ Acceptance:** patient can chat + hear reply.

---

## M3c · Conversational dialogue loop (talk ↔ reply ↔ talk)

> **Why:** Today the mic is a one-shot form (“speak need → cards”). The finished product must feel like **talking to Serah**: normal conversation stays in chat; caregiver-finding turns call **VEHMF**; after cards, the patient can keep talking to refine or ask questions.

### Step 15f — Turn router (CHAT | MATCH | REFINE | ACTION | EMERGENCY)

**Goal:** classify each spoken/typed turn before choosing a backend.  
**Tasks:**
- `POST /api/v1/dialogue/turn` (or extend voice intent) returns `{ route, intent?, reply_hint? }`
- Routes:
  - **CHAT** — general care questions, empathy, how Care Plus works → Serah (Gemini or local stub)
  - **MATCH** — patient wants caregivers → extract goal fields → VEHMF (`POST /match/`)
  - **REFINE** — after RESULTS (“closer”, “Tamil”, “female”, “about #2”) → update filters → re-run VEHMF
  - **ACTION** — “request the first one” / “book” → hire CTA (Step 23+)
  - **EMERGENCY** — urgent language → emergency weights + alert UX
- Never let Gemini invent caregiver rankings; ranking stays VEHMF + XAI only

**✅ Acceptance:** fixture phrases map to correct routes (≥90% on a small labeled set); MATCH never returns Gemini-picked IDs.

**Depends on:** 15d, 20. **Feeds:** 15g–15j, 23.

### Step 15g — Conversation session + memory

**Goal:** multi-turn context without losing chips/results.  
**Tasks:** `DialogueSession` (user, lang, route history, last `MatchRun`, open questions); store last N turns; FSM stays on RESULTS while chatting about matches; “New request” clears session.  
**✅ Acceptance:** after cards, asking “why is #1 ranked high?” keeps RESULTS visible and answers with that run’s XAI; “find someone else” triggers REFINE/MATCH.

### Step 15h — Unified Neural Core conversation loop (UI)

**Goal:** one mic, continuous dialogue — not a separate Serah panel forever.  
**Tasks:** after every turn, Serah speaks/shows a short reply; mic re-arms (or “Tap to continue”); LISTENING ↔ THINKING ↔ (SPEAKING|CHAT_REPLY|MATCHING|RESULTS); Goal Ring still fills on MATCH/REFINE; chat bubbles for Serah lines.  
**✅ Acceptance:** user can: greet → ask diabetes tip (CHAT) → “find me a Sinhala caregiver” (MATCH → cards) → “someone closer” (REFINE) without leaving the home screen.

### Step 15i — Post-match conversational refine

**Goal:** talk to adjust the shortlist.  
**Tasks:** map refine phrases → filter deltas (language, care_level, max_distance_km, specialty); re-call VEHMF; push via existing `ws/match/`; highlight changed ranks.  
**✅ Acceptance:** “only Tamil speakers within 5 km” updates cards; latency badge still shown.

### Step 15j — Local / Gemini policy for dialogue

**Goal:** clear AI split so cost and PDPA stay sane.  
**Tasks:** document + env: `DIALOGUE_CHAT_BACKEND=gemini|stub`; MATCH/REFINE always local VEHMF; stub chat for CI/offline; rate-limit Gemini chat; audit every turn route.  
**✅ Acceptance:** with no `GEMINI_API_KEY`, CHAT still replies via stub; MATCH still returns real seed caregivers.

---

## M4 · VEHMF v1 + Match UX

### Step 16 — Domain models + Sri Lanka seed ✅

### Step 17 — Embeddings + FAISS index build ✅ **DONE**

**Done:** pluggable embedders (`hash` lean default, optional `e5`); `build_caregiver_index`
writes L2-normalized vectors to DB + `ml/artifacts/caregivers.faiss`; lazy load +
`POST /api/v1/match/cbf/` preview; query “diabetes Sinhala intermediate Colombo”
ranks diabetes specialists highest on seed data.
**✅ Acceptance:** rebuild reproducible with seed; nearest-neighbor query returns sensible caregivers.

### Step 18 — AHP weights ✅ **DONE**

**Done:** NumPy principal-eigenvector AHP solver; CR check (< 0.1);
`config/ahp_weights.json` (α≈0.48 CBF, β≈0.07 CF, γ≈0.20 Geo, δ≈0.24 Trust);
emergency override `[0.80,0.05,0.05,0.10]`; env comma overrides; `build_ahp_weights`;
`GET /api/v1/match/weights/`.
**✅ Acceptance:** weights sum to 1, CR < 0.1, overrideable via env for emergencies.

### Step 19 — VEHMF engine + `/api/v1/match` ✅ **DONE**

**Done:** `VEHMFEngine` fuses CBF (FAISS) + CF stub + PostGIS geo + trust with AHP
weights; XAI explanation; `MatchRun`/`MatchResult` persistence; consent-gated
`POST /api/v1/match/` returns ranked list + breakdown + latency.
**✅ Acceptance:** POST match returns ranked list + breakdown + explanation; unit tests on fusion math; p95 < 800 ms on seed caregivers.

### Step 20 — Match WebSocket + result UX ✅ **DONE**

**Done:** JWT `ws/match/{patient_id}/`; push from `POST /match/`; HomePage SPEAKING → MATCHING → RESULTS; `MatchResultCards` (score, CBF/CF/geo/trust bars, XAI, distance, latency badge); Request CTA placeholder → Step 23.
**✅ Acceptance:** end-to-end voice phrase yields explained cards in UI; FSM reaches RESULTS.

---

## M4b · Marketplace browse (old `/caregivers` + profile pages)

### Step 20b — Caregiver search & filter API ✅ **DONE**

**Done:** `GET /caregivers/?q=&language=&specialty=&city=&care_level=&available=&near=lon,lat&radius_km=` with pagination; `city` + `is_available` on profile; only `is_active` listed.
**✅ Acceptance:** filters combine; pagination; only `is_active` caregivers.

### Step 20c — Browse UI (web)

**Goal:** searchable caregiver directory.  
**Tasks:** list + filter chips; map pins (Leaflet/MapLibre); empty/error states.  
**✅ Acceptance:** seed caregivers visible; filter by Sinhala + diabetes works.

### Step 20d — Caregiver public detail page

**Goal:** old `profile/<uuid>` rebuilt.  
**Tasks:** bio, certs, languages, specialties, trust, approximate area, reviews teaser, Request CTA.  
**✅ Acceptance:** deep-linkable `/caregivers/:id`; audited view if health-adjacent fields shown.

### Step 20e — Availability flag + soft presence

**Goal:** old `is_available`.  
**Tasks:** caregiver toggles availability; match/browse honor it.  
**✅ Acceptance:** unavailable caregivers hidden from match top-N (or ranked last with badge).

---

## M5 · Personalization (CF)

### Step 21 — Interaction log + CF training offline

**Tasks:** `Interaction` (view/request/accept/complete/rate); `ml/train_cf.py` (`implicit` ALS); Celery beat nightly; artifact versioning.  
**✅ Acceptance:** trains on seed interactions; produces per-user scores.

### Step 22 — Blend CF into VEHMF fusion

**✅ Acceptance:** four-factor fusion; offline NDCG/MAP improves vs CBF-only; feature flag to disable CF.

---

## M5b · Profiles & onboarding (old Profile richness)

### Step 22b — Patient onboarding wizard

**Goal:** height, weight, blood type, city, languages, known conditions, medications, allergies, emergency contact.  
**Tasks:** multi-step web form; validates against vocab; writes `PatientProfile` + health snapshot.  
**✅ Acceptance:** new patient cannot request care until profile ≥80% complete (configurable).

### Step 22c — Caregiver onboarding wizard

**Goal:** NIC/ID verify placeholder, city, languages, certifications upload metadata, specialties, years experience, bio, service radius.  
**✅ Acceptance:** caregiver inactive in match until onboarding complete + admin/auto approve flag.

### Step 22d — Profile photo & document metadata

**Tasks:** media storage (S3 or local volume); virus scan stub; size/type limits.  
**✅ Acceptance:** upload + serve authenticated; no public open bucket.

### Step 22e — Profile completion % API

**✅ Acceptance:** both roles see completion meter; matches old dashboard UX intent.

### Step 22f — Email OTP optional second factor

**Goal:** old OTP flow, correctly ordered (OTP before session elevation).  
**Tasks:** issue OTP, verify, elevate JWT claims `otp_verified`.  
**✅ Acceptance:** sensitive actions (hire, pay, records) require OTP when enabled.

---

## M6 · Hire lifecycle (old checkout → accept → link)

### Step 23 — `CareRequest` model + API

**Goal:** replace overloaded Email-as-hire.  
**Tasks:** states `draft|pending|accepted|rejected|cancelled|expired`; patient→caregiver; snapshot of intent/match scores; expiry job.  
**✅ Acceptance:** patient creates request from match card; caregiver sees inbox; duplicate active request blocked.

### Step 24 — Caregiver inbox accept/reject

**Tasks:** list/detail actions; notifications; on accept → provisional `CareRelationship` pending payment.  
**✅ Acceptance:** accept/reject audited; patient notified.

### Step 25 — `CareRelationship` (active care link)

**Goal:** old `PatientCaregiverLink`.  
**Tasks:** active/inactive; start/end; one active primary caregiver rule (configurable).  
**✅ Acceptance:** end agreement frees caregiver availability; history retained.

### Step 26 — Patient “current caregiver” + caregiver “current patient” views

**✅ Acceptance:** role home dashboards show active link + quick actions (message, records, end).

### Step 27 — Lead appointments (marketing form)

**Goal:** old `Appointment` leads.  
**Tasks:** public form → admin queue; optional auto-email ack.  
**✅ Acceptance:** submission stored; admin can mark contacted.

### Step 28 — Request expiry + reminder Celery tasks

**✅ Acceptance:** pending > N hours auto-expires; reminder email/push at N/2.

---

## M7 · Catalog, checkout & payments (old CareType/Food/Hospital + mock pay)

### Step 29 — Catalog models

**Tasks:** `CarePackage` (basic/intermediate/advanced, LKR), `AddOn` (hospital/food/etc.), admin-managed.  
**✅ Acceptance:** seeded LKR packages; API list.

### Step 30 — Checkout session

**Tasks:** select package + add-ons + days; bind to `CareRequest`; persist line items (no hardcoded radios lost).  
**✅ Acceptance:** checkout creates priced `Order` in `awaiting_payment`.

### Step 31 — PaymentIntent abstraction

**Tasks:** interface `MockProvider` (dev) + `PayHereProvider` stub; never mark paid without provider confirm webhook.  
**✅ Acceptance:** mock pay succeeds only via explicit confirm endpoint; webhook signature verified in stub tests.

### Step 32 — Payment UI (web)

**Tasks:** order summary, pay CTA, success/failure pages; no fake card numbers required in mock mode.  
**✅ Acceptance:** paid order activates `CareRelationship`; caregiver `is_available` updates per policy.

### Step 33 — Invoices / receipts PDF or email

**✅ Acceptance:** patient receives receipt with LKR breakdown; audit row written.

---

## M8 · Medical records (old MedicalRecord)

### Step 34 — MedicalRecord model + encrypted fields

**Tasks:** description, disease/condition FK to vocab, attachments; pgcrypto or app-level AES for sensitive text.  
**✅ Acceptance:** only patient + linked caregiver + admin/auditor can read; access audited.

### Step 35 — Upload / list / download APIs

**✅ Acceptance:** multipart upload; MIME allowlist; max size; signed download URLs.

### Step 36 — Caregiver medical records UI for current patient

**✅ Acceptance:** caregiver sees records only while relationship active.

### Step 37 — Patient records vault UI

**✅ Acceptance:** patient CRUD own records; soft-delete with audit.

---

## M9 · Messaging & notifications

### Step 38 — MessageThread between patient ↔ caregiver

**Goal:** replace static `chat.html` + Email-as-comms.  
**Tasks:** thread per relationship; text messages; read receipts.  
**✅ Acceptance:** both parties exchange messages in realtime (WS) or polling fallback.

### Step 39 — Notification preferences

**Tasks:** email/push toggles per event type.  
**✅ Acceptance:** user can disable marketing but not security alerts.

### Step 40 — Email notification templates

**Tasks:** request received, accepted, payment due, anomaly alert.  
**✅ Acceptance:** templates render si/ta/en; Celery sends in staging.

### Step 41 — Web push (VAPID) for web app

**✅ Acceptance:** browser push on care request when granted.

---

## M10 · Reviews & trust

### Step 42 — Review model + moderation

**Goal:** old Review with real ratings.  
**Tasks:** 1–5 stars + text; status pending/approved/rejected; only after completed relationship.  
**✅ Acceptance:** pending hidden from public; admin approve publishes.

### Step 43 — Trust score recompute job

**Tasks:** blend ratings, completion rate, response time → `trust_score`.  
**✅ Acceptance:** new approved review updates caregiver trust within job SLA.

### Step 44 — Reviews on caregiver detail UI

**✅ Acceptance:** average + recent reviews visible; empty state polite.

---

## M11 · Health monitoring (upgrade beyond old static profile)

### Step 45 — Timescale `HEALTH_METRIC` hypertable + ingest API

**✅ Acceptance:** simulated stream ingests; window aggregates fast.

### Step 46 — Anomaly daemon (rules first)

**✅ Acceptance:** hypo/hyperglycemia trend → `health_critical` event.

### Step 47 — Emergency dynamic VEHMF re-weight + re-match

**✅ Acceptance:** emergency weights α↑; nearest certified advanced caregiver pushed over WS.

### Step 48 — Alerts UX (EMERGENCY Neural Core state)

**✅ Acceptance:** rose brain + alert banner + link to emergency match.

### Step 49 — FCM/APNs mobile push for alerts

**✅ Acceptance:** device receives push in staging.

---

## M12 · Scheduling

### Step 50 — Shift / availability calendar models

**✅ Acceptance:** caregiver publishes weekly slots; patient sees free slots.

### Step 51 — Booking API with Redlock

**✅ Acceptance:** concurrent book → exactly one success.

### Step 52 — Calendar UX (web)

**✅ Acceptance:** book/cancel flows; timezone Asia/Colombo.

### Step 53 — Conflict fallback re-match

**✅ Acceptance:** loser auto-offered next-best caregiver (VEHMF).

---

## M13 · Admin console (old analytical dashboard)

### Step 54 — Admin app shell (web, role=admin|auditor)

**Tasks:** users table, role filters, disable account.  
**✅ Acceptance:** admin-only routes; auditor read-only where required.

### Step 55 — Vocab & catalog admin UI

**✅ Acceptance:** CRUD conditions, packages, add-ons.

### Step 56 — Analytics charts API

**Goal:** old email_status / role distribution charts.  
**Tasks:** requests by status, role counts, match latency p95, active relationships.  
**✅ Acceptance:** Chart.js/Recharts dashboard matches API.

### Step 57 — Leads / subscribers / appointments queue

**✅ Acceptance:** admin processes marketing leads.

### Step 58 — Audit log browser

**✅ Acceptance:** filter by actor/action/date; export CSV.

---

## M14 · i18n & accessibility

### Step 59 — UI i18n (Sinhala / Tamil / English)

**Tasks:** `packages/core` message catalogs; language switcher persists.  
**✅ Acceptance:** key screens fully translated; RTL not required.

### Step 60 — Accessibility pass

**Tasks:** focus traps, ARIA live regions (already partial), contrast, keyboard Neural Core controls.  
**✅ Acceptance:** axe clean on auth + home + results; reduced-motion OK.

### Step 61 — Content & empty-state copy polish

**✅ Acceptance:** no lorem; Sri Lanka–appropriate microcopy.

---

## M15 · Mobile (Expo RN)

### Step 62 — Expo bootstrap + shared packages
### Step 63 — Auth + role navigation
### Step 64 — Neural Core (Skia) + voice → intent
### Step 65 — Match results + request caregiver
### Step 66 — Caregiver inbox + messaging
### Step 67 — Push alerts + store build profiles  

**✅ Acceptance (M15):** Android + iOS patient voice→match→request; caregiver accept; alert push.

---

## M16 · Compliance & hardening

### Step 68 — pgcrypto / field encryption on health + intent
### Step 69 — Right-to-erasure + FAISS eviction + data export (JSON/PDF)
### Step 70 — TLS 1.3, security headers, rate limits, CORS lockdown
### Step 71 — Load & concurrency tests (match p95, booking Redlock)

**✅ Acceptance:** compliance checklist signed; load targets met.

---

## M17 · Ship

### Step 72 — CI/CD (build, test, push images, migrate)
### Step 73 — Deploy VM + observability (logs, metrics, Sentry)
### Step 74 — Play Store + App Store submissions
### Step 75 — Launch checklist (PDPA notices, support email, backups, runbooks)

**✅ Acceptance:** production URL live; apps in review/live; runbooks in `docs/ops/`.

---

## Parallel tracks (optional acceleration)

| Track | Steps | When |
|-------|-------|------|
| A · Research core | 17→20 ✅ | Done |
| B · Vocab + Serah + **dialogue loop** | 15b→15j | After 20; can overlap 20b–22 |
| C · Marketplace UI | 20b→20e | After 16; before or after dialogue |
| D · Hire/pay | 23→33 | After 20 (needs Request CTA); ACTION route in 15f wires later |
| E · Mobile | 62→67 | After web patient flow stable (≈ after 33 + 15h) |

---

## Working agreement

1. Branch `feat/stepN-<slug>` off updated `main`.
2. State goal + files touched.
3. Many focused commits OK.
4. Prove acceptance.
5. **Push**; PR → **merge**.
6. Update `PROGRESS.md`.
7. Next step = new branch.

Rules: `.cursor/rules/git-workflow.mdc`.

---

## Next up

**Step 20c — Browse UI (web)** (`feat/step20c-browse-ui`), or Step 15c / 21 CF.
