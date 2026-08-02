# Load & concurrency tests (Step 71)

Acceptance targets (ARCHITECTURE + DEVELOPMENT_PLAN):

| Check | Target |
|-------|--------|
| Match `latency_ms` **p95** | **&lt; 800 ms** on seeded caregivers (hash embedder / lean VEHMF) |
| Concurrent shift booking | **Exactly one** `201` / one `BOOKED` row under Redlock |

## In-process Django tests (CI-friendly)

With Docker backend + Redis:

```bash
docker compose -f infra/docker-compose.yml exec -T backend \
  python manage.py test apps.matching.tests.test_load_concurrency -v2
```

Env knobs:

```bash
MATCH_P95_MS=800
MATCH_SAMPLES=25
BOOK_CONCURRENCY=8
```

Tagged `@tag("load")` — still runs in the default suite (fast with `EMBEDDING_BACKEND=hash`).

Existing 2-way smoke: `apps.matching.tests.test_shift_booking.ConcurrentShiftBookingTests`.

## HTTP harness (real uvicorn + Redis)

```bash
# Match p95 (patient with AI consent; caregivers indexed)
python backend/scripts/load_step71.py --mode match \
  --base-url http://localhost:8000 \
  --match-email patient@example.com --match-password '…' \
  --samples 50 --p95-ms 800

# Redlock race (N patients, same caregiver window)
python backend/scripts/load_step71.py --mode redlock \
  --caregiver-id 1 --slot-id 1 --concurrency 8 \
  --patient-creds 'a@x.com:pw,b@x.com:pw,…'
```

If match loops hit **429**, raise `DRF_THROTTLE_MATCH` for the load run (Step 70).

## Compliance checklist (Step 71)

- [x] Match p95 budget documented (800 ms) and covered by automated test
- [x] Redlock concurrent booking covered (2-way + 8-way)
- [x] HTTP harness for Docker API available under `backend/scripts/`
- [ ] Sign-off: run both modes against staging before production cutover (Step 73+)
