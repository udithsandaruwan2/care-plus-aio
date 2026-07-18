# Care Plus — Progress Log

> **Purpose:** running record of _what's done_ and _what's next_, so work can resume
> from any device. Committed to git (syncs across machines). Updated **feature by feature**.  
> Full plan: [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) **v0.2 (75 steps)** ·  
> Vision (Old→New): [docs/PRODUCT_VISION.md](docs/PRODUCT_VISION.md) ·  
> Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) ·  
> Frontend: [docs/FRONTEND.md](docs/FRONTEND.md)

_Last updated: 2026-07-18 — Full product plan v0.2 from Old Care Plus reference. Steps 1–16 done. **Next: Step 17** (embeddings + FAISS)._

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

- 🔜 **Step 17** — Embeddings + FAISS index  
- ⬜ **18** AHP weights · **19** VEHMF + `/match` · **20** WS + result UX  

### Expanded product tracks (from Old Care Plus)

| Milestone | Steps | Status |
|-----------|-------|--------|
| **M3b** Medical vocab + Serah chat | 15b–15e | ⬜ |
| **M4b** Marketplace browse/map/detail | 20b–20e | ⬜ |
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

**Progress:** ~16 / 75 steps (~21%). Voice understanding works; matching marketplace hire/pay/records/mobile still ahead.

---

## What works today (user-facing)

- Register / login (JWT), consent gate, Neural Core voice UI  
- Speak (si/ta/en) → structured intent → chips + Goal Ring; clarify loop  
- Seeded caregivers in DB (API list); no ranked match UI yet  

---

## Changelog (newest first)

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
