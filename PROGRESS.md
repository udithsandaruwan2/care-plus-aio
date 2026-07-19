# Care Plus — Progress Log

> **Purpose:** running record of _what's done_ and _what's next_, so work can resume
> from any device. Committed to git (syncs across machines). Updated **feature by feature**.  
> Full plan: [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) **v0.3 (~80 steps)** ·  
> Vision (Old→New): [docs/PRODUCT_VISION.md](docs/PRODUCT_VISION.md) ·  
> Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) ·  
> Frontend: [docs/FRONTEND.md](docs/FRONTEND.md)

_Last updated: 2026-07-19 — Step 20d caregiver detail page done. Next: 20e availability toggle._

---

## Git workflow (cross-device)

| Rule | Detail |
|------|--------|
| **Author** | Always **Udith Sandaruwan** `<developer.udithsandaruwan@gmail.com>` — never `Care Plus Dev` / agent |
| **How** | Terminal only: `git add` → `git -c user.name=… -c user.email=… commit` → `git push` → `gh pr …` |
| **Branch** | One branch per feature/step (`feat/stepN-<slug>`, `fix/…`, `chore/…`) off `main` |
| **Commits** | Many focused commits per branch OK |
| **Push** | Always push after development (and when switching devices / end of session) |
| **Merge** | When the branch is complete (or when necessary): PR → merge into `main` |
| **Next feature** | New branch from updated `main` — never pile features on one branch |

Rules file: `.cursor/rules/git-workflow.mdc` (includes identity + terminal commit recipe).

---

## How to resume on a new device

```bash
git clone https://github.com/udithsandaruwan2/care-plus-aio.git "Care Plus"
cd "Care Plus"
cp .env.example .env                      # fill in secrets (GEMINI_API_KEY, etc.)
docker compose -f infra/docker-compose.yml up -d --build
curl -fsS http://localhost:8000/api/v1/health/   # expect {"status":"ok","db":"ok","redis":"ok"}
pnpm --filter @care-plus/web dev --host 127.0.0.1 --port 5173
```

Notes:

- Backend runs in Docker on **Python 3.11** (host Python version irrelevant).
- Host DB port is **5433** (container internal 5432) to avoid clashing with a local Postgres.
- Local reference only: `Old Care Plus/` (gitignored) — old Lumora/Care Plus HND app for product shape.
- Requires Docker + ~5–10 GB free disk.

---

## Decisions locked (lean profile)

See DEVELOPMENT_PLAN §0. Highlights: Web Speech + whisper fallback · VEHMF matching ·
TimescaleDB · e5-base embeddings · Aurora Neural UI · Care Plus brand · canonical medical vocab ·
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

### Active track — research match loop

- ✅ **Step 17** — Embeddings + FAISS `IndexFlatIP` (hash embedder default; e5 optional); `build_caregiver_index` / `query_caregiver_index`; `POST /match/cbf/`. Branch `feat/step17-embeddings-faiss`.
- ✅ **Step 18** — AHP principal-eigenvector weights `[α,β,γ,δ]` (CR < 0.1); `config/ahp_weights.json`; env emergency override; `GET /match/weights/`. Branch `feat/step18-ahp-weights`.
- ✅ **Step 19** — `VEHMFEngine` (CBF+CF-stub+Geo+Trust+XAI); `MatchRun`/`MatchResult`; consent-gated `POST /api/v1/match/`. Branch `feat/step19-vehmf-engine`.
- ✅ **Step 20** — JWT `ws/match/{id}/` + push; MatchResultCards; SPEAKING→MATCHING→RESULTS. Branch `feat/step20-match-ux`.
- ✅ **Step 15b** — Canonical `ConditionTerm` vocab (≥37); `GET /vocab/conditions/`; stub maps ඩෙංගු→`dengue`. Branch `feat/step15b-medical-vocab`.
- ✅ **Step 20b** — Caregiver search/filter/geo API + pagination (`city`, `is_available`). Branch `feat/step20b-caregiver-search`.
- ✅ **Step 20c** — `/caregivers` browse UI (chips + Leaflet map). Branch `feat/step20c-browse-ui`.
- ✅ **Step 20d** — Caregiver public detail `/caregivers/:id` + audited API. Branch `feat/step20d-caregiver-detail`.
- ⬜ **M3c Steps 15f–15j** — Conversational dialogue (partially shipped via `/voice/turn/` + TTS; formalize remaining)
- 🔜 **Step 20e** — Availability flag + soft presence

### Expanded product tracks (from Old Care Plus)

| Milestone | Steps | Status |
|-----------|-------|--------|
| **M3b** Medical vocab + Serah chat | 15b–15e | 15b ✅ · 15c–e ⬜ |
| **M3c** Conversational dialogue loop | 15f–15j | ░ partial (`/voice/turn/` + TTS shipped) |
| **M4b** Marketplace browse/map/detail | 20b–20e | 20b–20d ✅ · 20e ⬜ |
| **M5** CF personalization | 21–22 | ⬜ |
| **M5b** Rich onboarding / OTP | 22b–22f | ⬜ |
| **M6** Hire lifecycle (`CareRequest`) | 23–28 | ⬜ |
| **M7** Catalog + checkout + payments | 29–33 | ⬜ |
| **M8** Medical records | 34–37 | ⬜ |
| **M9** Messaging + notifications | 38–41 | ⬜ |
| **M10** Reviews → trust | 42–44 | ⬜ |
| **M11** Health monitoring + emergency | 45–49 | ⬜ |
| **M12** Scheduling + Redlock | 50–53 | ⬜ |
| **M13** Admin console | 54–58 | ⬜ |
| **M14** i18n + a11y | 59–61 | ⬜ |
| **M15** Mobile Expo | 62–67 | ⬜ |
| **M16** Compliance | 68–71 | ⬜ |
| **M17** Ship | 72–75 | ⬜ |

**Progress:** ~20 / ~80 steps. Voice → VEHMF → cards works (one-shot). Conversational loop planned as **M3c (15f–15j)**.

---

## What works today (user-facing)

- Register / login (JWT), consent gate, Neural Core voice UI  
- Speak (si/ta/en) → structured intent → chips + Goal Ring; clarify loop  
- Seeded caregivers + CBF preview + **full VEHMF `POST /match/`** (ranked + breakdown + XAI)  
- AHP weights + emergency override  
- **Match result cards** + JWT `ws/match/{patient_id}/` push; FSM → RESULTS  
- **Not yet:** multi-turn “talk like Serah” (chat vs match router) — see M3c  

---

## Changelog (newest first)

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
