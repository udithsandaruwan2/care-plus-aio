# Care Plus

**Care Plus** is a research-grade, data-driven AI ecosystem that matches **patients** with
**caregivers** using multilingual (Sinhala / Tamil / English) **voice input**, a hybrid
recommendation engine (**VEHMF**), and **real-time health monitoring** that dynamically
re-ranks matches during medical anomalies.

Built for **speed** (voice → ranked list in **< 800 ms**) and **resource efficiency**
(the lean stack fits in **≤ 4 GB RAM / 2 vCPU**, no GPU required at runtime).

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

## Status

Pre-development. The architecture is designed; the next step is to confirm the
[open decisions](docs/ARCHITECTURE.md#15-open-decisions) and generate the Phase 0 scaffold.

## Tech stack (lean profile)

**Backend:** Django 4.2 · DRF · Channels (ASGI) · Gemini 1.5 Flash · FAISS · LightFM/implicit ·
NumPy/SciPy (AHP) · PostgreSQL + PostGIS + TimescaleDB · Redis · Celery · Firebase FCM.

**Web:** Vite · React 18 · TypeScript · Tailwind · Framer Motion · react-three-fiber (Neural Core) · Zustand · TanStack Query.

**Mobile:** Expo · React Native · TypeScript · react-native-skia · Reanimated · expo-notifications (Android + iOS).

**Shared:** pnpm workspaces + Turborepo monorepo (`packages/ui-tokens`, `api-client`, `core`).
